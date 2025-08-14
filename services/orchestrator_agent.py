import base64
import os
import logging
import asyncio
import json
import re
from typing import Optional, List, Dict, Union

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from thefuzz.fuzz import token_set_ratio # Corrigido para importar diretamente a função

from agno.agent import Agent, RunResponse
from agno.models.google import Gemini
from agno.memory.v2.memory import Memory
from agno.media import Audio, Image, Video
from agno.workflow.v2.workflow import Workflow, WorkflowRunResponse
from agno.workflow.v2.steps import Step, Steps
from agno.workflow.v2.router import Router
from agno.workflow.v2.types import StepInput, StepOutput

from core import schemas
from core.database import DATABASE_URL
from core.schemas import (
    AIResponse, FinalResponseData, AnaliseDeIntencao, BuscaDeProduto, OrderState, TarefaIdentificada, FreightDetails
)
from crud import tenant_crud, product_crud, user_address_crud
from agno.memory.v2.db.postgres import PostgresMemoryDb
from core.vector_db import VectorDBManager
from services.agents.receptionist_agent import get_receptionist_agent
from services.agents.order_taking_agent import get_order_taking_agent
from services.agents.response_formulation_agent import get_response_formulation_agent
from services.agents.file_understanding_agent import get_file_understanding_agent
from services.tools import ferramenta_busca_avancada_produtos, geocode_address, freight_calculator, get_contextual_suggestions_tool, get_applicable_promotions_tool
from services.product_service import ProductService
from services.state_manager import state_manager


logger = logging.getLogger(__name__)

def extract_json_from_response(response_content: Union[str, dict, list]) -> Optional[Dict]:
    if isinstance(response_content, (dict, list)):
        return response_content
    response_content_str = str(response_content)
    match = re.search(r"```json\n(.*?)\n```", response_content_str, re.DOTALL)
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON do markdown: {e}")
            return None
    try:
        return json.loads(response_content_str)
    except (json.JSONDecodeError, TypeError):
        return None

class OrchestratorAgent:
    def __init__(self, db: Session, session_id: str, tenant_id: str, user_id: str, api_key: str):
        logger.debug(f"OrchestratorAgent initialized for session {session_id}")
        self.db = db
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.api_key = api_key
        
        self.RECEPTIONIST_MODEL_ID = "models/gemini-1.5-flash-latest"
        self.RESPONSE_FORMULATION_MODEL_ID = "models/gemini-1.5-flash-latest"
        self.FILE_UNDERSTANDING_MODEL_ID = "models/gemini-1.5-pro-latest"
        self.ORDER_TAKING_AGENT_MODEL_ID = "models/gemini-1.5-flash-latest"

        self.memory_db = PostgresMemoryDb(table_name="user_memories", db_url=DATABASE_URL)
        self.memory = Memory(db=self.memory_db)

        # Agent Definitions
        self.receptionist_agent = get_receptionist_agent(model_id=self.RECEPTIONIST_MODEL_ID, api_key=self.api_key, db=self.db, tenant_id=self.tenant_id)
        self.order_taking_agent = get_order_taking_agent(model_id=self.ORDER_TAKING_AGENT_MODEL_ID, api_key=self.api_key, memory=self.memory, db=self.db, tenant_id=self.tenant_id)
        self.response_formulation_agent = get_response_formulation_agent(model_id=self.RESPONSE_FORMULATION_MODEL_ID, api_key=self.api_key, memory=self.memory, db=self.db, tenant_id=self.tenant_id)

        # Step Definitions
        self.receptionist_step = Step(name="receptionist", agent=self.receptionist_agent)
        self.order_taking_step = Step(name="order_taking", executor=self._handle_order_taking_executor)
        self.product_search_step = Step(name="product_search", executor=self._handle_product_search_executor)
        self.human_handoff_step = Step(name="human_handoff", executor=self._handle_human_handoff_executor)
        self.menu_step = Step(name="menu", executor=self._handle_menu_request_executor)
        self.pass_through_step = Step(name="pass_through", executor=self._pass_through_executor)
        self.geocode_step = Step(name="geocode", executor=self._execute_geocode_if_needed)
        self.freight_calculation_step = Step(name="freight_calculation", executor=self._execute_freight_calculation)
        self.rag_search_step = Step(name="rag_search", executor=self._execute_rag_search)
        self.suggestion_gathering_step = Step(name="suggestion_gathering", executor=self._suggestion_gathering_executor)
        self.response_formulation_step = Step(name="response_formulation", agent=self.response_formulation_agent)

        # Main Router
        self.main_router = Router(
            name="Main Router",
            selector=self._route_to_data_collection_step,
            choices=[
                self.order_taking_step,
                self.product_search_step,
                self.human_handoff_step,
                self.menu_step,
                self.rag_search_step,
                self.pass_through_step,
                self.geocode_step,
                self.freight_calculation_step
            ]
        )

        # Workflow Definition
        self.workflow = Workflow(
            name="Chatbot Workflow",
            steps=[
                self.receptionist_step,
                self.main_router,
                self.suggestion_gathering_step,
                self.response_formulation_step,
            ]
        )

    async def _suggestion_gathering_executor(self, step_input: StepInput) -> StepOutput:
        logger.info("EXECUTOR: Executando _suggestion_gathering_executor para encontrar upsells.")
        
        search_results = step_input.additional_data.get("search_results")
        
        if not search_results or not isinstance(search_results, list) or len(search_results) == 0:
            logger.info("Nenhum produto encontrado no contexto, pulando a busca por sugestões.")
            return StepOutput(content="Nenhuma sugestão para adicionar.")

        product_context = search_results[0]
        product_id = product_context.get("id_produto")

        if not product_id:
            logger.warning("Produto encontrado nos resultados, mas sem ID. Pulando sugestões.")
            return StepOutput(content="Produto sem ID, sem sugestões.")

        suggestions_json, promotions_json = await asyncio.gather(
            run_in_threadpool(get_contextual_suggestions_tool.entrypoint, product_id=product_id, agent=self),
            run_in_threadpool(get_applicable_promotions_tool.entrypoint, tenant_id=self.tenant_id, order_state_json="{}", agent=self)
        )
        
        try:
            suggestions = json.loads(suggestions_json)
            promotions = json.loads(promotions_json)
        except json.JSONDecodeError:
            suggestions = []
            promotions = []
            logger.error("Erro ao decodificar JSON das ferramentas de sugestão/promoção.")

        step_input.additional_data["suggestions"] = suggestions
        step_input.additional_data["promotions"] = promotions
        
        logger.info(f"Encontradas {len(suggestions)} sugestões e {len(promotions)} promoções.")
        
        return StepOutput(content="Sugestões e promoções coletadas.")

    async def _handle_menu_request_executor(self, step_input: StepInput) -> StepOutput:
        logger.info("EXECUTOR: Executando _handle_menu_request_executor.")
        
        step_input.additional_data['send_menu_requested'] = True
        canned_response = "Claro! Aqui está o nosso cardápio."
        step_input.additional_data["rag_context"] = canned_response
        return StepOutput(content=canned_response)

    async def _execute_geocode_if_needed(self, step_input: StepInput) -> StepOutput:
        logger.info("EXECUTOR: Verificando necessidade de geocodificação.")
        additional_data = step_input.additional_data or {}
        
        if additional_data.get("client_latitude") and additional_data.get("client_longitude"):
            logger.info("Coordenadas já existem no contexto. Pulando geocodificação.")
            return StepOutput(content="Coordenadas já fornecidas.")

        receptionist_output = additional_data.get('receptionist_output')
        address = None
        if isinstance(receptionist_output, schemas.AnaliseDeIntencao) and receptionist_output.tarefas:
            address = receptionist_output.tarefas[0].detalhes
        
        if not address:
            address = step_input.message
        
        if not address or not isinstance(address, str) or not address.strip():
            logger.warning("Nenhum endereço de texto válido fornecido para geocodificação. Pulando.")
            return StepOutput(content=json.dumps({"error": "address_required"}))
        
        logger.info(f"Executando geocodificação para o endereço: {address}")
        coords_json = await geocode_address.entrypoint(address=address)
        coords = json.loads(coords_json)
        
        if coords.get("error"):
            raise Exception(f"Erro de geocodificação: {coords.get('error')}")
        
        additional_data['client_latitude'] = coords.get('lat')
        additional_data['client_longitude'] = coords.get('lng')
        logger.info(f"Geocodificação bem-sucedida. Lat: {coords.get('lat')}, Lng: {coords.get('lng')}")
        
        return StepOutput(content=f"Coordenadas encontradas para {address}")

    async def _execute_freight_calculation(self, step_input: StepInput) -> StepOutput:
        logger.info("EXECUTOR: Executando cálculo de frete determinístico.")
        additional_data = step_input.additional_data or {}
        
        previous_content = step_input.previous_step_content
        if isinstance(previous_content, str):
            try:
                content_dict = json.loads(previous_content)
                if content_dict.get("error") == "address_required":
                    logger.warning("Cálculo de frete pulado pois o endereço é necessário.")
                    return StepOutput(content=previous_content)
            except (json.JSONDecodeError, TypeError):
                pass

        client_lat = additional_data.get("client_latitude")
        client_lng = additional_data.get("client_longitude")
        tenant_id = additional_data.get("tenant_id")

        if not all([client_lat, client_lng, tenant_id]):
            missing = [k for k, v in {"client_latitude": client_lat, "client_longitude": client_lng, "tenant_id": tenant_id}.items() if not v]
            logger.warning(f"Dados insuficientes para calcular o frete. Faltando: {', '.join(missing)}")
            return StepOutput(content=json.dumps({"error": "address_required", "message": f"Faltando: {', '.join(missing)}"}))

        freight_result_json = await freight_calculator.entrypoint(
            client_latitude=float(client_lat),
            client_longitude=float(client_lng),
            tenant_id=tenant_id,
            db=self.db
        )
        
        freight_result = json.loads(freight_result_json)
        if freight_result.get("error"):
            raise Exception(f"Erro na ferramenta de cálculo de frete: {freight_result.get('error')}")

        additional_data['freight_details'] = schemas.FreightDetails(**freight_result)
        logger.info(f"Cálculo de frete bem-sucedido. Detalhes: {freight_result}")
        
        return StepOutput(content=json.dumps(freight_result))

    async def _pass_through_executor(self, step_input: StepInput) -> StepOutput:
        logger.info("ORCHESTRATOR: Executing _pass_through_executor.")
        return StepOutput(content=step_input.previous_step_content)

    async def _handle_human_handoff_executor(self, step_input: StepInput) -> StepOutput:
        logger.info("ORCHESTRATOR: Executing _handle_human_handoff_executor.")
        step_input.additional_data['human_handoff_needed'] = True
        return StepOutput(content={})

    async def _handle_menu_request_executor(self, step_input: StepInput) -> StepOutput:
        logger.info("ORCHESTRATOR: Executing _handle_menu_request_executor.")
        step_input.additional_data['send_menu_requested'] = True
        return StepOutput(content={})

    async def _handle_product_search_executor(self, step_input: StepInput) -> StepOutput:
        logger.info("EXECUTOR: Executando _handle_product_search_executor com ProductService (Lógica Aprimorada).")
        receptionist_output = step_input.additional_data.get('receptionist_output')

        if not isinstance(receptionist_output, schemas.BuscaDeProduto):
            logger.warning(f"Input para _handle_product_search_executor não era BuscaDeProduto, mas {type(receptionist_output)}. Pulando busca.")
            step_input.additional_data["search_results"] = []
            return StepOutput(content={})

        product_service = ProductService(db=self.db, tenant_id=self.tenant_id)
        found_products = await run_in_threadpool(product_service.find_product_filtered, search_criteria=receptionist_output)

        if found_products:
            logger.info(f"Busca de produto encontrou {len(found_products)} resultado(s).")
            search_results = [{
                "id_produto": p.id_produto,
                "nome_produto": p.nome_produto,
                "descricao_produto": p.descricao_produto,
                "preco_base": p.preco_base
            } for p in found_products]
            step_input.additional_data["search_results"] = search_results
        else:
            logger.info(f"Nenhum produto encontrado para os critérios: '{receptionist_output.model_dump_json()}'")
            step_input.additional_data["search_results"] = []

        return StepOutput(content={})

    async def _handle_order_taking_executor(self, step_input: StepInput) -> StepOutput:
        logger.info("EXECUTOR: Executing _handle_order_taking_executor com ProductService (Lógica Aprimorada).")
        order_state: OrderState = step_input.additional_data.get("order_state")
        receptionist_output: AnaliseDeIntencao = step_input.additional_data.get('receptionist_output')

        if not isinstance(receptionist_output, AnaliseDeIntencao) or not receptionist_output.tarefas:
            logger.warning("Input para order_taking_executor não é uma tarefa válida.")
            return StepOutput(content={})

        task = receptionist_output.tarefas[0]
        product_service = ProductService(db=self.db, tenant_id=self.tenant_id)

        if task.tipo_tarefa == 'adicionar_item':
            if not task.detalhes:
                logger.warning("Tentativa de adicionar item sem detalhes (nome do produto).")
                step_input.additional_data["clarification_needed"] = "Por favor, especifique qual item você deseja adicionar."
                return StepOutput(content="Clarificação necessária.")

            # --- NOVO: Usar find_product_filtered e lidar com ambiguidade ---
            # Converte os detalhes da tarefa em um schema BuscaDeProduto para a busca filtrada
            search_criteria = schemas.BuscaDeProduto(termos_gerais=task.detalhes.split())
            found_products = await run_in_threadpool(product_service.find_product_filtered, search_criteria=search_criteria)

            if len(found_products) == 1:
                found_product = found_products[0]
                logger.info(f"Produto encontrado via ProductService: {found_product.nome_produto}. Adicionando ao pedido.")
                order_item = schemas.OrderItem(
                    product_id=found_product.id_produto,
                    product_name=found_product.nome_produto,
                    quantity=task.quantidade or 1,
                    unit_price=found_product.preco_base,
                    total_price=(found_product.preco_base * (task.quantidade or 1))
                )
                order_state.items.append(order_item)
                step_input.additional_data["product_added_successfully"] = True
                step_input.additional_data["response_text_override"] = f"Adicionado {found_product.nome_produto} ao seu pedido."
            elif len(found_products) > 1:
                # Lidar com ambiguidade: pedir clarificação
                product_names = [p.nome_produto for p in found_products]
                clarification_msg = f"Encontrei mais de uma opção para '{task.detalhes}': {', '.join(product_names)}. Qual deles você gostaria?"
                logger.warning(f"Ambiguidade na busca de produto: {clarification_msg}")
                step_input.additional_data["clarification_needed"] = clarification_msg
                step_input.additional_data["response_text_override"] = clarification_msg
            else:
                logger.warning(f"Produto não encontrado para '{task.detalhes}'.")
                step_input.additional_data["product_not_found"] = True
                step_input.additional_data["response_text_override"] = f"Desculpe, não encontrei '{task.detalhes}' no cardápio."
            # --- FIM NOVO ---

        elif task.tipo_tarefa == 'remover_item':
            if not task.detalhes:
                logger.warning("Tentativa de remover item sem detalhes (nome do produto).")
                step_input.additional_data["clarification_needed"] = "Por favor, especifique qual item você deseja remover."
                return StepOutput(content="Clarificação necessária.")

            item_removed = False
            for i in range(len(order_state.items) - 1, -1, -1):
                similarity = token_set_ratio(task.detalhes, order_state.items[i].product_name)
                if similarity > 85:
                    logger.info(f"Removendo item '{order_state.items[i].product_name}' do pedido.")
                    del order_state.items[i]
                    item_removed = True
                    step_input.additional_data["response_text_override"] = f"Removido {task.detalhes} do seu pedido."
                    break
            if not item_removed:
                step_input.additional_data["item_not_found_in_order"] = True
                step_input.additional_data["response_text_override"] = f"Não encontrei '{task.detalhes}' no seu pedido."
            step_input.additional_data["item_removed_successfully"] = item_removed

        elif task.tipo_tarefa == 'modificar_item': # NOVO: Lógica básica para modificar item
            if not task.detalhes:
                logger.warning("Tentativa de modificar item sem detalhes.")
                step_input.additional_data["clarification_needed"] = "Por favor, especifique qual item você deseja modificar e como."
                return StepOutput(content="Clarificação necessária.")
            
            # Por enquanto, apenas um placeholder. A lógica real de modificação (adicionar opcional, mudar tamanho)
            # seria mais complexa e dependeria de como os opcionais são modelados no OrderItem.
            logger.info(f"Tentativa de modificar item: {task.detalhes}. Funcionalidade ainda não totalmente implementada.")
            step_input.additional_data["response_text_override"] = f"Desculpe, a modificação de '{task.detalhes}' ainda não é suportada."

        elif task.tipo_tarefa == 'confirmar_pedido':
            logger.info("Finalizando o pedido.")
            order_state.is_finalized = True
            # NOVO: Gerar resumo do pedido para confirmação
            if order_state.items:
                summary_lines = [f"{item.quantity}x {item.product_name}" for item in order_state.items]
                total_price = sum(item.total_price for item in order_state.items)
                order_summary_text = f"Seu pedido atual: {'; '.join(summary_lines)}. Total: R$ {total_price:.2f}."
                step_input.additional_data["order_summary_for_confirmation"] = order_summary_text
                step_input.additional_data["response_text_override"] = order_summary_text + " Confirma?"
            else:
                step_input.additional_data["response_text_override"] = "Seu pedido está vazio. Gostaria de adicionar algo?"

        step_input.additional_data["order_state"] = order_state
        return StepOutput(content={})

    async def _route_to_data_collection_step(self, step_input: StepInput) -> Union[Step, List[Step]]:
        logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - Roteador: 1. Entrando em _route_to_data_collection_step (Lógica Unificada).")
        receptionist_output = self._validate_receptionist_output(step_input.previous_step_content)
        logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - Roteador: 2. Saída do recepcionista validada: {receptionist_output}")
        step_input.additional_data['receptionist_output'] = receptionist_output

        if isinstance(receptionist_output, BuscaDeProduto):
            logger.info("Roteando para a busca de produtos (BuscaDeProduto direta).")
            return self.product_search_step

        elif isinstance(receptionist_output, AnaliseDeIntencao) and receptionist_output.tarefas:
            primeira_tarefa = receptionist_output.tarefas[0]
            task_type = primeira_tarefa.tipo_tarefa
            details = primeira_tarefa.detalhes or ""
            logger.info(f"Roteando para a tarefa: {task_type}")

            product_keywords = ['produto', 'cardápio', 'menu', 'comida', 'bebida', 'preço', 'tem', 'quais']
            is_product_question = any(keyword in details.lower() for keyword in product_keywords)

            if task_type == 'menu' or (task_type == 'fazer_pergunta_geral' and is_product_question):
                logger.info(f"Tarefa '{task_type}' detectada como pergunta de produto. Convertendo para BuscaDeProduto.")
                step_input.additional_data['receptionist_output'] = schemas.BuscaDeProduto(termos_gerais=details.split())
                return self.product_search_step

            if task_type == 'calcular_frete':
                logger.info("Roteando para a sequência de cálculo de frete.")
                return [self.geocode_step, self.freight_calculation_step]
            
            task_map = {
                'falar_com_humano': self.human_handoff_step,
                'adicionar_item': self.order_taking_step,
                'remover_item': self.order_taking_step,
                'confirmar_pedido': self.order_taking_step,
                'horario_funcionamento': self.rag_search_step
            }
            
            selected_step = task_map.get(task_type)
            if selected_step:
                return selected_step

        logger.info("Nenhuma rota específica para produto ou tarefa encontrada, usando o rag_search_step como fallback.")
        return self.rag_search_step

    async def _execute_rag_search(self, step_input: StepInput) -> StepOutput:
        logger.info("EXECUTOR: Executando busca RAG para pergunta geral.")
        query = step_input.message
        tenant_id = step_input.additional_data.get("tenant_id")
        
        if not query or not tenant_id:
            return StepOutput(content="")

        try:
            vector_db_manager = VectorDBManager(self.db, collection_name=tenant_id)
            search_results = await run_in_threadpool(vector_db_manager.search_documents, query=query, k=1)
            
            if not search_results:
                return StepOutput(content="")

            context = "\n".join([result.get('page_content', '') for result in search_results])
            step_input.additional_data["rag_context"] = context
            logger.info(f"Contexto RAG encontrado: {context}")
            return StepOutput(content=context)
        except Exception as e:
            logger.error(f"Erro durante a busca RAG: {e}", exc_info=True)
            return StepOutput(content="")

    async def _execute_rag_search(self, step_input: StepInput) -> StepOutput:
        logger.info("EXECUTOR: Executando busca RAG para pergunta geral.")
        query = step_input.message
        tenant_id = step_input.additional_data.get("tenant_id")
        
        if not query or not tenant_id:
            return StepOutput(content="")

        try:
            vector_db_manager = VectorDBManager(self.db, collection_name=tenant_id)
            search_results = await run_in_threadpool(vector_db_manager.search_documents, query=query, k=1)
            
            if not search_results:
                return StepOutput(content="")

            context = "\n".join([result.get('page_content', '') for result in search_results])
            step_input.additional_data["rag_context"] = context
            logger.info(f"Contexto RAG encontrado: {context}")
            return StepOutput(content=context)
        except Exception as e:
            logger.error(f"Erro durante a busca RAG: {e}", exc_info=True)
            return StepOutput(content="")

    def _validate_receptionist_output(self, content: any) -> any:
        logger.debug(f"Validando saída do recepcionista: {content}")
        if isinstance(content, (AnaliseDeIntencao, BuscaDeProduto)):
            return content
        
        json_data = extract_json_from_response(content)
        if json_data:
            data_to_process = json_data.get('AnaliseDeIntencao', json_data)

            if 'tarefas' in data_to_process and isinstance(data_to_process['tarefas'], list) and data_to_process['tarefas']:
                tarefa = data_to_process['tarefas'][0]
                if 'endereco' in tarefa and isinstance(tarefa['endereco'], dict):
                    logger.debug("Encontrado objeto 'endereco', convertendo para 'detalhes'.")
                    endereco_obj = tarefa['endereco']
                    address_parts = [endereco_obj.get('logradouro'), endereco_obj.get('numero'), endereco_obj.get('bairro'), endereco_obj.get('cidade'), endereco_obj.get('estado'), endereco_obj.get('cep')]
                    tarefa['detalhes'] = ', '.join(filter(None, address_parts))
                    del tarefa['endereco']

            try:
                if 'BuscaDeProduto' in json_data: return schemas.BuscaDeProduto(**json_data['BuscaDeProduto'])
                if 'AnaliseDeIntencao' in json_data: return schemas.AnaliseDeIntencao(**json_data['AnaliseDeIntencao'])
                if 'termos_gerais' in data_to_process: return schemas.BuscaDeProduto(**data_to_process)
                if 'tarefas' in data_to_process: return schemas.AnaliseDeIntencao(**data_to_process)
            except Exception as e:
                logger.error(f"Falha ao validar JSON do recepcionista: {e}")
        
        logger.warning(f"Conteúdo do recepcionista não reconhecido: {content}")
        return AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa="fazer_pergunta_geral", detalhes=str(content))])

    async def _get_order_state(self) -> OrderState:
        return await run_in_threadpool(state_manager.get_order_state, self.session_id) or OrderState()

    async def _save_order_state(self, state: OrderState):
        await run_in_threadpool(state_manager.save_order_state, self.session_id, state)

    async def process_message(self, message: str, personality_prompt: str, **kwargs) -> AIResponse:
        logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 1. Entrando em process_message.")
        order_state = await self._get_order_state()
        logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 2. Estado do pedido recuperado.")
        
        try:
            file_summary = None
            if kwargs.get('file_content') and kwargs.get('mimetype'):
                logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 3a. Arquivo detectado, chamando _handle_file_understanding.")
                summary, file_type = await self._handle_file_understanding(kwargs['file_content'], kwargs['mimetype'])
                logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 3b. _handle_file_understanding concluído.")
                message = summary
                file_summary = schemas.FileSummary(summary_text=summary, file_type=file_type) if file_type else None

            if not message or not message.strip():
                logger.warning(f"ORCHESTRATOR_TRACE: [{self.session_id}] - Mensagem vazia, retornando diretamente.")
                return AIResponse(response_text="Por favor, envie uma mensagem de texto.", human_handoff=False, send_menu=False)

            additional_data = {"original_message": message, "order_state": order_state, "personality_prompt": personality_prompt, "tenant_id": self.tenant_id, "file_summary": file_summary, "user_id": self.user_id, **kwargs}
            logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 4. Dados adicionais preparados. Chamando o workflow.arun().")
            
            workflow_response: WorkflowRunResponse = await self.workflow.arun(message=message, additional_data=additional_data)
            logger.info(f"ORCHESTRATOR: [{self.session_id}] - self.workflow.arun() concluído.")
            logger.debug(f"ORCHESTRATOR_DEBUG: Resposta completa do workflow: {workflow_response!r}")

            logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 5. workflow.arun() finalizado. Processando conteúdo final.")
            final_content = workflow_response.content
            if not isinstance(final_content, FinalResponseData):
                 logger.warning(f"Conteúdo final inesperado: {final_content}. Encapsulando.")
                 final_content = FinalResponseData(text_response=str(final_content))

            last_step_data = getattr(workflow_response, 'additional_data', {})
            
            if not final_content.freight_details:
                final_freight_details = last_step_data.get('freight_details')
                if final_freight_details and isinstance(final_freight_details, FreightDetails):
                    logger.warning("Agente de formulação não incluiu freight_details. Adicionando manualmente do contexto do workflow.")
                    final_content.freight_details = final_freight_details

            logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 6. Salvando estado do pedido.")
            await self._save_order_state(order_state)
            
            logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 7. FIM process_message, retornando resposta.")
            return AIResponse(
                response_text=final_content.text_response,
                human_handoff=last_step_data.get('human_handoff_needed', False),
                send_menu=last_step_data.get('send_menu_requested', False),
                freight_details=final_content.freight_details,
                file_summary=file_summary
            )
        except Exception as e:
            logger.error(f"Erro crítico no process_message: {e}", exc_info=True)
            return AIResponse(response_text=f"Desculpe, ocorreu um erro interno: {e}", human_handoff=True, send_menu=False)

    async def _handle_file_understanding(self, file_content: bytes, mimetype: str) -> tuple[str, Optional[str]]:
        logger.info(f"[{self.session_id}] - INICIO _handle_file_understanding")
        try:
            agent = get_file_understanding_agent(model_id=self.FILE_UNDERSTANDING_MODEL_ID, api_key=self.api_key, db=self.db, tenant_id=self.tenant_id)
            prompt = "Analise este arquivo e descreva seu conteúdo. Se for um áudio, transcreva-o."
            media_map = {"audio": Audio, "image": Image, "video": Video}
            media_type_str = mimetype.split('/')[0]

            if media_type_str in media_map:
                media_class = media_map[media_type_str]
                media_input = media_class(content=file_content)
                media_arg = {f"{media_type_str}s": [media_input]}
                response = await agent.arun(prompt, **media_arg)
                if response and response.content and hasattr(response.content, 'summary'):
                    return response.content.summary, mimetype
            
            logger.warning(f"Tipo de arquivo não suportado ou análise falhou: {mimetype}")
            logger.info(f"[{self.session_id}] - FIM _handle_file_understanding (falha)")
            return f"Não foi possível processar o arquivo ({mimetype}).", None
        except Exception as e:
            logger.error(f"Erro na análise do arquivo: {e}", exc_info=True)
            logger.info(f"[{self.session_id}] - FIM _handle_file_understanding (erro)")
            return "Ocorreu um erro ao analisar o arquivo.", None

    async def load_data_to_vector_db(self):
        logger.info(f"[{self.session_id}] - Carregando dados de produtos para o VectorDB do tenant {self.tenant_id}")
        vector_db_manager = VectorDBManager(self.db, collection_name=self.tenant_id)
        
        products = await run_in_threadpool(product_crud.get_products_by_tenant, self.db, self.tenant_id)
        
        tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, self.db, self.tenant_id)
        general_info = tenant.config_ai if tenant else ""

        document_text = general_info + "\n\n--- Cardápio Completo ---"
        
        if not products:
            logger.info(f"[{self.session_id}] - Nenhum produto encontrado para o tenant {self.tenant_id}.")
        else:
            products_by_category = {}
            for product in products:
                category = product.categoria_produto or "Diversos"
                if category not in products_by_category:
                    products_by_category[category] = []
                products_by_category[category].append(product)

            for category, items in products_by_category.items():
                document_text += f"\n**{category.upper()}**\n"
                for item in items:
                    price_str = f"R$ {item.preco_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    document_text += f"- {item.nome_produto}: {item.descricao_produto} - {price_str}\n"
        
        texts = [document_text]
        metadatas = [{"source": "full_store_info_and_menu", "tenant_id": self.tenant_id}]
        
        await run_in_threadpool(vector_db_manager.add_documents, texts, metadatas)
        logger.info(f"[{self.session_id}] - Informações da loja e {len(products)} produtos carregados como um único documento no VectorDB.")
