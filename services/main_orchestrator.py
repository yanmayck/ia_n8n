# -*- coding: utf-8 -*-
"""
Este módulo contém a classe OrchestratorAgent, que é o cérebro central
para o processamento de mensagens de um chatbot de pedidos. Ele gerencia
o fluxo de trabalho (workflow), coordena diferentes agentes de IA especializados
e mantém o estado da conversa e do pedido.
"""
import asyncio
import json
import logging
import re
from functools import partial
from typing import Dict, List, Optional, Union

# Importações de bibliotecas externas e de componentes da aplicação.
from agno.agent import RunResponse
from agno.media import Audio, Image, Video
from agno.memory.v2.db.postgres import PostgresMemoryDb
from agno.memory.v2.memory import Memory
from agno.workflow.v2.router import Router
from agno.workflow.v2.steps import Step
from agno.workflow.v2.types import StepInput, StepOutput
from agno.workflow.v2.workflow import Workflow, WorkflowRunResponse
from core import  schemas
from core.database import DATABASE_URL
from core.schemas import (
    AIResponse,
    AnaliseDeIntencao,
    BuscaDeProduto,
    FinalResponseData,
    FreightDetails,
    OrderState,
    TarefaIdentificada,
)
from core.vector_db import VectorDBManager
from crud import product_crud, promocao_crud, tenant_crud 
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from thefuzz.fuzz import token_set_ratio

# Importação de agentes, serviços e ferramentas especializados.
from services.agents.file_understanding_agent import get_file_understanding_agent
from services.agents.order_taking_agent import get_order_taking_agent
from services.agents.receptionist_agent import get_receptionist_agent
from services.agents.response_formulation_agent import get_response_formulation_agent
from services.business_logic.product_service import ProductService
from services.integrations.platform_client import save_order_to_platform
from services.state_manager import state_manager
from services.tools.geolocation import freight_calculator, geocode_address
from services.tools.product import (
    get_applicable_promotions_tool,
    get_contextual_suggestions_tool,
)

# Configuração do logger para este módulo.
logger = logging.getLogger(__name__)


def extract_json_from_response(
    response_content: Union[str, dict, list],
) -> Optional[Dict]:
    """
    Extrai um objeto JSON de uma string, que pode estar ou não formatada como um bloco de código markdown.

    Args:
        response_content: O conteúdo da resposta, que pode ser uma string, dicionário ou lista.

    Returns:
        Um dicionário representando o JSON extraído, ou None se a extração falhar.
    """
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


def formatar_resumo_pedido(order_state: schemas.OrderState) -> str:
    """
    Cria uma string de resumo de pedido formatada de forma determinística para o usuário.

    Args:
        order_state: O estado atual do pedido.

    Returns:
        Uma string formatada com o resumo do pedido (itens, subtotal, frete, total e pagamento).
    """
    resumo_parts = ["*Resumo do Pedido:\n-----------------------------------"]
    subtotal = sum(item.total_price for item in order_state.items)

    for item in order_state.items:
        resumo_parts.append(
            f"- {item.quantity}x {item.product_name}.... R$ {item.total_price:,.2f}".replace(
                ".", ","
            )
        )

    resumo_parts.append("-----------------------------------")
    resumo_parts.append(f"*Subtotal:* R$ {subtotal:,.2f}".replace(".", ","))

    frete = order_state.freight_details.cost if order_state.freight_details else 0.0
    resumo_parts.append(f"*Taxa de Entrega:* R$ {frete:,.2f}".replace(".", ","))

    total = subtotal + frete
    resumo_parts.append(f"\n*TOTAL:* *R$ {total:,.2f}*".replace(".", ","))

    if order_state.payment_method:
        resumo_parts.append(f"\n*Pagamento:* {order_state.payment_method.capitalize()}")

    return "\n".join(resumo_parts)


class OrchestratorAgent:
    """
    O cérebro do sistema de IA.

    Esta classe orquestra o fluxo de trabalho (workflow) completo para processar uma
    mensagem de usuário. Ela é responsável por:
    1. Inicializar todos os agentes especializados (recepcionista, etc.).
    2. Definir os passos (steps) que compõem o workflow (ex: analisar intenção,
       buscar produto, calcular frete).
    3. Usar um roteador (`Router`) para direcionar a conversa para o passo correto
       com base na intenção do usuário.
    4. Gerenciar o estado da conversa e do pedido (`OrderState`) entre as mensagens.
    5. Executar o workflow e retornar a resposta final e estruturada.
    """

    def __init__(
        self,
        db: Session,
        session_id: str,
        tenant_id: str,
        user_id: str,
        api_key: str,
    ):
        """
        Inicializa o OrchestratorAgent.

        Args:
            db (Session): A sessão do banco de dados para operações de CRUD.
            session_id (str): O ID da sessão da conversa.
            tenant_id (str): O ID do tenant (loja) ao qual a conversa pertence.
            user_id (str): O ID do usuário final.
            api_key (str): A chave de API do Gemini a ser usada para as chamadas de IA.
        """
        logger.debug(f"ORCHESTRATOR_FLOW: [{session_id}] - Entering __init__")
        self.db = db
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.api_key = api_key

        self.RECEPTIONIST_MODEL_ID = "gemini-2.0-flash-lite"
        self.RESPONSE_FORMULATION_MODEL_ID = "gemini-2.0-flash-lite"
        self.FILE_UNDERSTANDING_MODEL_ID = "models/gemini-2.5-flash-lite"
        self.ORDER_TAKING_AGENT_MODEL_ID = "gemini-2.0-flash-lite"

        self.memory_db = PostgresMemoryDb(
            table_name="user_memories", db_url=DATABASE_URL
        )
        self.memory = Memory(db=self.memory_db)
        self.session_state = {"db": self.db, "tenant_id": self.tenant_id}

        logger.debug(f"ORCHESTRATOR_FLOW: [{session_id}] - Initializing agents...")
        self.receptionist_agent = get_receptionist_agent(
            model_id=self.RECEPTIONIST_MODEL_ID,
            api_key=self.api_key,
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        self.order_taking_agent = get_order_taking_agent(
            model_id=self.ORDER_TAKING_AGENT_MODEL_ID,
            api_key=self.api_key,
            memory=self.memory,
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        self.response_formulation_agent = get_response_formulation_agent(
            model_id=self.RESPONSE_FORMULATION_MODEL_ID,
            api_key=self.api_key,
            memory=self.memory,
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        logger.debug(f"ORCHESTRATOR_FLOW: [{session_id}] - Agents initialized.")

        logger.debug(f"ORCHESTRATOR_FLOW: [{session_id}] - Defining steps...")
        self.receptionist_step = Step(
            name="receptionist", agent=self.receptionist_agent
        )
        self.order_taking_step = Step(
            name="order_taking", executor=partial(self._handle_order_taking_executor)
        )
        self.product_search_step = Step(
            name="product_search",
            executor=partial(self._handle_product_search_executor),
        )
        self.human_handoff_step = Step(
            name="human_handoff", executor=partial(self._handle_human_handoff_executor)
        )
        self.menu_step = Step(
            name="menu", executor=partial(self._handle_menu_request_executor)
        )
        self.pass_through_step = Step(
            name="pass_through", executor=partial(self._pass_through_executor)
        )
        self.geocode_step = Step(
            name="geocode", executor=partial(self._execute_geocode_if_needed)
        )
        self.freight_calculation_step = Step(
            name="freight_calculation",
            executor=partial(self._execute_freight_calculation),
        )
        self.rag_search_step = Step(
            name="rag_search", executor=partial(self._execute_rag_search)
        )
        self.suggestion_gathering_step = Step(
            name="suggestion_gathering",
            executor=partial(self._suggestion_gathering_executor),
        )
        self.greeting_step = Step(
            name="greeting", executor=partial(self._handle_greeting_executor)
        )
        self.ask_payment_method_step = Step(
            name="ask_payment_method",
            executor=partial(self._ask_payment_method_executor),
        )
        self.final_confirmation_step = Step(
            name="final_confirmation",
            executor=partial(self._final_confirmation_executor),
        )
        self.create_order_step = Step(
            name="create_order", executor=partial(self._create_order_executor)
        )
        self.response_formulation_step = Step(
            name="response_formulation",
            executor=partial(self._response_assembly_executor),
        )
        logger.debug(f"ORCHESTRATOR_FLOW: [{session_id}] - Steps defined.")

        self.main_router = Router(
            name="Main Router",
            selector=partial(self._route_to_data_collection_step),
            choices=[
                self.order_taking_step,
                self.product_search_step,
                self.human_handoff_step,
                self.menu_step,
                self.rag_search_step,
                self.pass_through_step,
                self.geocode_step,
                self.freight_calculation_step,
                self.greeting_step,
                self.ask_payment_method_step,
                self.final_confirmation_step,
                self.create_order_step,
            ],
        )

        self.workflow = Workflow(
            name="Chatbot Workflow",
            steps=[
                self.receptionist_step,
                self.main_router,
                self.suggestion_gathering_step,
                self.response_formulation_step,
            ],
        )
        logger.debug(f"ORCHESTRATOR_FLOW: [{session_id}] - __init__ finished.")

    async def _ask_payment_method_executor(self, step_input: StepInput) -> StepOutput:
        """Prepara o contexto para a IA perguntar a forma de pagamento."""
        logger.info("EXECUTOR: Preparando para perguntar a forma de pagamento.")
        context_message = "O cliente pediu para fechar o pedido. Pergunte a ele qual a forma de pagamento (Pix, Cartão ou Dinheiro) e aguarde a resposta."
        step_input.additional_data["rag_context"] = context_message
        return StepOutput(content=context_message)

    async def _final_confirmation_executor(self, step_input: StepInput) -> StepOutput:
        """Monta o resumo final do pedido e prepara a IA para pedir a confirmação."""
        logger.info("EXECUTOR: Preparando o resumo final do pedido.")
        additional_data = step_input.additional_data
        order_state: OrderState = additional_data.get("order_state")
        receptionist_output: AnaliseDeIntencao = additional_data.get(
            "receptionist_output"
        )

        if receptionist_output and receptionist_output.tarefas:
            task = receptionist_output.tarefas[0]
            if task.tipo_tarefa == "informar_metodo_pagamento" and isinstance(
                task.detalhes, str
            ):
                order_state.payment_method = task.detalhes
                logger.info(
                    f"Método de pagamento '{order_state.payment_method}' salvo no estado."
                )

        summary_string = formatar_resumo_pedido(order_state)

        context_message = f"Apresente este resumo para o cliente e peça uma confirmação final (sim ou não). Resumo: {summary_string}"
        step_input.additional_data["rag_context"] = context_message
        return StepOutput(content=context_message)

    async def _handle_human_handoff_executor(self, step_input: StepInput) -> StepOutput:
        """Prepara o contexto para transferir o atendimento a um humano."""
        logger.info("EXECUTOR: Executando _handle_human_handoff_executor.")
        context_message = "O usuário solicitou falar com um atendente humano. Prepare uma mensagem para transferi-lo."
        step_input.additional_data["rag_context"] = context_message
        step_input.additional_data["human_handoff_needed"] = True
        return StepOutput(content=context_message)

    async def _create_order_executor(self, step_input: StepInput) -> StepOutput:
        """Envia o pedido finalizado para a plataforma de gestão externa."""
        logger.info("EXECUTOR: Criando o pedido na plataforma externa.")
        additional_data = step_input.additional_data
        order_state: OrderState = additional_data.get("order_state")

        if order_state.status == "confirmed":
            return StepOutput(content="Este pedido já foi confirmado.")

        order_state.status = "confirmed"

        freight_details = order_state.freight_details
        subtotal = sum(item.total_price for item in order_state.items)
        freight_cost = freight_details.cost if freight_details else 0
        total_price = subtotal + freight_cost

        items_to_send = [item.model_dump() for item in order_state.items]
        address_to_send = order_state.address
        payment_to_send = order_state.payment_method

        try:
            await save_order_to_platform(
                user_id=self.user_id,
                tenant_id=self.tenant_id,
                items=items_to_send,
                total_price=total_price,
                db=self.db,
                address=address_to_send,
                payment_method=payment_to_send,
                freight_details=freight_details.model_dump()
                if freight_details
                else None,
            )
            logger.info("Pedido enviado com sucesso para a plataforma.")
            context_message = (
                "Pedido confirmado com sucesso! Agradeça ao cliente e encerre a conversa."
            )
        except Exception as e:
            logger.error(
                f"Falha ao enviar pedido para a plataforma: {e}", exc_info=True
            )
            context_message = "Tive um problema ao finalizar seu pedido na plataforma. Por favor, informe ao cliente e peça para ele tentar novamente em instantes."

        step_input.additional_data["rag_context"] = context_message
        return StepOutput(content=context_message)

    async def _handle_greeting_executor(self, step_input: StepInput) -> StepOutput:
        """Executor para lidar com uma saudação simples do usuário."""
        logger.info("EXECUTOR: Executando _handle_greeting_executor.")
        return StepOutput(content="ACTION:GREETING")

    async def _response_assembly_executor(self, step_input: StepInput) -> StepOutput:
        """Monta e formata a resposta final para o usuário usando o `response_formulation_agent`."""
        logger.info(
            "EXECUTOR: Montando a resposta final com injeção de contexto para a IA."
        )
        additional_data = step_input.additional_data or {}
        message_for_formulation = step_input.previous_step_content or step_input.message

        if isinstance(message_for_formulation, dict) and not message_for_formulation:
            message_for_formulation = step_input.message

        if message_for_formulation == "ACTION:GREETING":
            logger.info("Gerando saudação personalizada.")
            personality_prompt = additional_data.get(
                "personality_prompt", "Você é um assistente prestativo."
            )
            greeting_prompt = f"{personality_prompt}. Sua tarefa é criar uma saudação de boas-vindas calorosa e se apresentar brevemente. Não faça perguntas, apenas se apresente."
            text_generation_response = await self.response_formulation_agent.arun(
                message=greeting_prompt
            )
            generated_text = (
                str(text_generation_response.content.text_response)
                if text_generation_response.content
                else "Olá! Como posso ajudar?"
            )
            return StepOutput(content=FinalResponseData(text_response=generated_text))

        rag_context = additional_data.get("rag_context")
        final_freight_details = additional_data.get("order_state", OrderState()).freight_details
        human_handoff = additional_data.get("human_handoff_needed", False)
        send_menu = additional_data.get("send_menu_requested", False)

        context_parts = []
        if rag_context:
            context_parts.append(f"Contexto: {rag_context}")

        promotions = additional_data.get("promotions")
        if promotions:
            promo_texts = [
                f"'{p.get('nome_promocao')}' ({p.get('descricao_para_ia')})"
                for p in promotions
            ]
            context_parts.append(f"Promoções Aplicáveis: {', '.join(promo_texts)}")

        suggestions = additional_data.get("suggestions")
        if suggestions:
            sugg_texts = [f"'{s.get('nome')}'" for s in suggestions]
            context_parts.append(
                f"Sugestões de Itens Adicionais: {', '.join(sugg_texts)}"
            )

        final_prompt_message = message_for_formulation
        if context_parts:
            full_context = " | ".join(context_parts)
            final_prompt_message = (
                f"Com base estritamente no seguinte contexto, responda à pergunta do usuário. "
                f"Contexto: '{full_context}'. Pergunta do usuário: '{message_for_formulation}'"
            )
            logger.info(
                f"Prompt final para a IA com contexto injetado: {final_prompt_message}"
            )

        text_generation_response = await self.response_formulation_agent.arun(
            message=final_prompt_message, additional_data=additional_data
        )

        generated_text = (
            str(text_generation_response.content.text_response)
            if text_generation_response.content
            and hasattr(text_generation_response.content, "text_response")
            else str(text_generation_response.content)
        )

        final_response = FinalResponseData(
            text_response=generated_text,
            human_handoff_needed=human_handoff,
            send_menu_requested=send_menu,
            freight_details=final_freight_details,
        )
        logger.info(
            f"Resposta final montada: {final_response.model_dump_json(indent=2)}"
        )
        return StepOutput(content=final_response)

    async def _suggestion_gathering_executor(self, step_input: StepInput) -> StepOutput:
        """Coleta promoções aplicáveis e sugestões contextuais com base no estado do pedido."""
        logger.info("EXECUTOR: Executando _suggestion_gathering_executor para encontrar upsells e promoções.")

        additional_data = step_input.additional_data
        order_state: OrderState = additional_data.get("order_state")

        if not order_state or not order_state.items or order_state.status == "confirmed":
            logger.info("Pedido vazio ou confirmado. Pulando a busca por sugestões e promoções.")
            return StepOutput(content={})

        promocoes_ja_oferecidas = set(order_state.promocoes_oferecidas_ids or [])
        tasks = []

        order_state_json = order_state.model_dump_json()
        promotions_task = get_applicable_promotions_tool.entrypoint(
            tenant_id=self.tenant_id,
            order_state_json=order_state_json,
            agent=self,
        )
        tasks.append(promotions_task)

        last_item = order_state.items[-1]
        if hasattr(last_item, "product_id") and last_item.product_id:
            suggestions_task = get_contextual_suggestions_tool.entrypoint(
                product_id=last_item.product_id, agent=self
            )
            tasks.append(suggestions_task)
        else:
            suggestions_task = None

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            promotions_result = results[0]
            if isinstance(promotions_result, Exception):
                logger.error(f"Erro ao buscar promoções: {promotions_result}", exc_info=promotions_result)
                additional_data["promotions"] = []
            else:
                all_promotions = json.loads(promotions_result)
                new_promotions = [
                    p for p in all_promotions if p.get("id") not in promocoes_ja_oferecidas
                ]
                additional_data["promotions"] = new_promotions
                logger.info(f"Novas promoções a serem oferecidas: {additional_data['promotions']}")
                if new_promotions:
                    order_state.last_offered_promotion_id = new_promotions[0].get("id")
                    for p in new_promotions:
                        order_state.promocoes_oferecidas_ids.append(p.get("id"))

            if suggestions_task:
                suggestions_result = results[1]
                if isinstance(suggestions_result, Exception):
                    logger.error(f"Erro ao buscar sugestões: {suggestions_result}", exc_info=suggestions_result)
                    additional_data["suggestions"] = []
                else:
                    suggestions = json.loads(suggestions_result)
                    additional_data["suggestions"] = suggestions
                    logger.info(f"Sugestões encontradas: {additional_data['suggestions']}")

        except Exception as e:
            logger.error(f"Erro inesperado ao executar gather de sugestões/promoções: {e}", exc_info=True)
            additional_data["suggestions"] = []
            additional_data["promotions"] = []

        return StepOutput(content={})

    async def _route_to_data_collection_step(
        self,
        step_input: StepInput,
    ) -> Union[Step, List[Step]]:
        """
        Atua como o roteador principal do workflow, decidindo qual passo executar com base na intenção do usuário.
        """
        logger.debug(
            f"ORCHESTRATOR_FLOW: [{self.session_id}] - Entering _route_to_data_collection_step"
        )
        receptionist_output = self._validate_receptionist_output(
            step_input.previous_step_content
        )
        step_input.additional_data["receptionist_output"] = receptionist_output

        if not receptionist_output.tarefas:
            logger.warning(
                "Recepcionista não retornou tarefas. Usando RAG como fallback."
            )
            return self.rag_search_step

        task_types = {t.tipo_tarefa for t in receptionist_output.tarefas}

        if "saudacao" in task_types and len(task_types) == 1:
            return self.greeting_step
        if "calcular_frete" in task_types:
            logger.info("Roteando para geocodificar e calcular o frete.")
            return [self.geocode_step, self.freight_calculation_step]
        if "fechar_conta" in task_types:
            return self.ask_payment_method_step
        if "informar_metodo_pagamento" in task_types:
            return [
                self.geocode_step,
                self.freight_calculation_step,
                self.final_confirmation_step,
            ]
        if "confirmar_pedido" in task_types:
            return self.create_order_step

        task_map = {
            "falar_com_humano": self.human_handoff_step,
            "adicionar_item": self.order_taking_step,
            "remover_item": self.order_taking_step,
            "aceitar_oferta": self.order_taking_step,
            "menu": self.menu_step,
            "buscar_produto": self.product_search_step,
            "horario_funcionamento": self.rag_search_step,
        }
        steps_to_run = [task_map[task] for task in task_types if task in task_map]

        if not steps_to_run:
            logger.info("Nenhuma rota específica, usando RAG como fallback.")
            return self.rag_search_step

        logger.info(f"Roteando para: {[s.name for s in steps_to_run]}")
        return steps_to_run

    async def _execute_rag_search(self, step_input: StepInput) -> StepOutput:
        """Executa uma busca vetorial (RAG) para responder a perguntas gerais."""
        logger.info("EXECUTOR: Executando busca RAG para pergunta geral.")
        query = step_input.message
        tenant_id = step_input.additional_data.get("tenant_id")

        if not query or not tenant_id:
            return StepOutput(content="")

        try:
            vector_db_manager = VectorDBManager(self.db, collection_name=tenant_id)
            search_results = await run_in_threadpool(
                vector_db_manager.search_documents, query=query, k=1
            )

            if not search_results:
                return StepOutput(content="")

            context = "\n".join(
                [result.get("page_content", "") for result in search_results]
            )
            step_input.additional_data["rag_context"] = context
            logger.info(f"Contexto RAG encontrado: {context}")
            return StepOutput(content=context)
        except Exception as e:
            logger.error(f"Erro durante a busca RAG: {e}", exc_info=True)
            return StepOutput(content="")

    def _validate_receptionist_output(self, content: any) -> any:
        """Valida e normaliza a saída do agente recepcionista para um schema conhecido."""
        logger.debug(f"Validando saída do recepcionista: {content}")
        if isinstance(content, (AnaliseDeIntencao, BuscaDeProduto)):
            return content

        json_data = extract_json_from_response(content)
        if json_data:
            data_to_process = json_data
            if "AnaliseDeIntencao" in json_data:
                data_to_process = json_data["AnaliseDeIntencao"]
            elif "BuscaDeProduto" in json_data:
                data_to_process = json_data["BuscaDeProduto"]
            elif (
                json_data.get("dispositivo") == "ANALISE_DE_INTENCAO"
                and "parametros" in json_data
            ):
                data_to_process = json_data["parametros"]

            try:
                if (
                    "termos_gerais" in data_to_process
                    or "ingredientes_excluir" in data_to_process
                ):
                    return schemas.BuscaDeProduto(**data_to_process)
                if "tarefas" in data_to_process:
                    return schemas.AnaliseDeIntencao(**data_to_process)
            except Exception as e:
                logger.error(
                    f"Falha ao validar JSON do recepcionista após normalização: {e}"
                )

        logger.warning(f"Conteúdo do recepcionista não reconhecido: {content}")
        return AnaliseDeIntencao(
            tarefas=[
                TarefaIdentificada(
                    tipo_tarefa="fazer_pergunta_geral", detalhes=str(content)
                )
            ]
        )

    async def _get_order_state(self) -> OrderState:
        """Recupera o estado atual do pedido do gerenciador de estado (e.g., Redis)."""
        logger.debug(
            f"ORCHESTRATOR_FLOW: [{self.session_id}] - Entering _get_order_state"
        )
        return (
            await run_in_threadpool(state_manager.get_order_state, self.session_id)
            or OrderState()
        )

    async def _save_order_state(self, state: OrderState):
        """Salva o estado atualizado do pedido no gerenciador de estado."""
        logger.debug(
            f"ORCHESTRATOR_FLOW: [{self.session_id}] - Entering _save_order_state"
        )
        await run_in_threadpool(state_manager.save_order_state, self.session_id, state)

    async def _handle_product_search_executor(self, step_input: StepInput) -> StepOutput:
        """Executa uma busca de produto e formata o resultado."""
        logger.info(
            "EXECUTOR: Executando _handle_product_search_executor com ProductService."
        )

        receptionist_output = step_input.additional_data.get("receptionist_output")
        search_criteria = None

        if isinstance(receptionist_output, schemas.BuscaDeProduto):
            search_criteria = receptionist_output
        elif isinstance(receptionist_output, schemas.AnaliseDeIntencao):
            for task in receptionist_output.tarefas:
                if task.tipo_tarefa == "buscar_produto" and isinstance(
                    task.detalhes, schemas.BuscaDeProduto
                ):
                    search_criteria = task.detalhes
                    break

        if not search_criteria:
            logger.warning(
                f"Não foi possível extrair critérios de busca válidos do input: {receptionist_output}. Pulando busca."
            )
            step_input.additional_data["search_results"] = []
            return StepOutput(content={})

        product_service = ProductService(db=self.db, tenant_id=self.tenant_id)
        found_products = await run_in_threadpool(
            product_service.find_product_filtered, search_criteria=search_criteria
        )

        if found_products:
            product_names = [p.nome_produto for p in found_products]
            response_text = f"Encontrei os seguintes produtos: {', '.join(product_names)}."
        else:
            response_text = "Desculpe, não encontrei nenhum produto que corresponda à sua busca."
        
        step_input.additional_data["rag_context"] = response_text
        step_input.additional_data["search_results"] = [p.model_dump() for p in found_products]

        return StepOutput(content=response_text)

    async def _handle_order_taking_executor(self, step_input: StepInput) -> StepOutput:
        """Processa tarefas relacionadas à manipulação do pedido (adicionar, remover, aceitar oferta)."""
        logger.info("EXECUTOR: Executando _handle_order_taking_executor com ProductService.")

        order_state: OrderState = step_input.additional_data.get("order_state")
        receptionist_output: AnaliseDeIntencao = step_input.additional_data.get(
            "receptionist_output"
        )
        confirmation_messages = []

        if (
            not isinstance(receptionist_output, AnaliseDeIntencao)
            or not receptionist_output.tarefas
        ):
            logger.warning("Input para order_taking_executor não é uma tarefa válida.")
            return StepOutput(content="")

        product_service = ProductService(db=self.db, tenant_id=self.tenant_id)

        for task in receptionist_output.tarefas:
            task_type = task.tipo_tarefa
            details = task.detalhes

            if task_type == "adicionar_item":
                if not details: continue

                search_criteria = None
                if isinstance(details, str):
                    search_criteria = schemas.BuscaDeProduto(termos_gerais=details.split())
                elif isinstance(details, dict):
                    search_criteria = schemas.BuscaDeProduto(**details)
                elif isinstance(details, schemas.BuscaDeProduto):
                    search_criteria = details

                if not search_criteria: continue

                found_products = await run_in_threadpool(
                    product_service.find_product_filtered, search_criteria=search_criteria
                )

                if len(found_products) == 1:
                    product = found_products[0]
                    quantity = getattr(task, "quantidade", 1) or 1
                    order_item = schemas.OrderItem(
                        product_id=product.id_produto,
                        product_name=product.nome_produto,
                        quantity=quantity,
                        unit_price=product.preco_base,
                        total_price=product.preco_base * quantity,
                    )
                    order_state.items.append(order_item)
                    confirmation_messages.append(f"Item '{product.nome_produto}' adicionado.")
                else:
                    confirmation_messages.append("Não consegui encontrar esse item. Poderia tentar de outra forma?")

            elif task_type == "remover_item":
                if not details: continue
                
                item_name_to_remove = details if isinstance(details, str) else " ".join(details.get("termos_gerais", []))
                item_removed = False
                for i in range(len(order_state.items) - 1, -1, -1):
                    if token_set_ratio(item_name_to_remove, order_state.items[i].product_name) > 85:
                        removed_item_name = order_state.items.pop(i).product_name
                        confirmation_messages.append(f"Item '{removed_item_name}' removido.")
                        item_removed = True
                        break
                if not item_removed:
                    confirmation_messages.append(f"Não encontrei o item '{item_name_to_remove}' no seu pedido.")

            elif task_type == "aceitar_oferta":
                promo_id = order_state.last_offered_promotion_id
                if not promo_id:
                    confirmation_messages.append("Desculpe, não encontrei uma oferta para aceitar.")
                    continue

                promocao = await run_in_threadpool(promocao_crud.get_promocao, self.db, promo_id)
                if promocao and promocao.acao_json and promocao.acao_json.get("tipo_desconto") == "brinde":
                    brinde_item = schemas.OrderItem(
                        product_id=0, product_name=promocao.nome_promocao,
                        quantity=1, unit_price=0.0, total_price=0.0
                    )
                    order_state.items.append(brinde_item)
                    confirmation_messages.append(f"Ótimo! Adicionei seu brinde: {promocao.nome_promocao}.")
                else:
                    confirmation_messages.append(f"Promoção '{promocao.nome_promocao}' aplicada!")
                
                order_state.last_offered_promotion_id = None

        final_confirmation = ". ".join(confirmation_messages)
        step_input.additional_data["confirmation_message"] = final_confirmation
        return StepOutput(content=final_confirmation)

    async def load_data_to_vector_db(self):
        """Carrega informações da loja e do cardápio para o banco de dados vetorial (RAG)."""
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
        logger.info(f"[{self.session_id}] - Informações da loja e {len(products)} produtos carregados no VectorDB.")

    async def _handle_menu_request_executor(self, step_input: StepInput) -> StepOutput:
        """Executor para lidar com uma solicitação de envio do cardápio."""
        logger.info("EXECUTOR: Executando _handle_menu_request_executor.")
        step_input.additional_data["send_menu_requested"] = True
        canned_response = "Claro! Aqui está o nosso cardápio."
        step_input.additional_data["rag_context"] = canned_response
        return StepOutput(content=canned_response)

    async def _execute_geocode_if_needed(self, step_input: StepInput) -> StepOutput:
        """Verifica se as coordenadas do cliente são necessárias e as obtém a partir de um endereço."""
        logger.info("EXECUTOR: Verificando necessidade de geocodificação.")
        additional_data = step_input.additional_data or {}

        if additional_data.get("client_latitude") and additional_data.get("client_longitude"):
            logger.info("Coordenadas já existem. Pulando geocodificação.")
            return StepOutput(content="Coordenadas já fornecidas.")

        receptionist_output = additional_data.get("receptionist_output")
        address = None

        if isinstance(receptionist_output, schemas.AnaliseDeIntencao):
            for task in receptionist_output.tarefas:
                if task.tipo_tarefa == "calcular_frete" and isinstance(task.detalhes, str):
                    address = task.detalhes
                    break
        
        if not address:
            logger.warning("Nenhum endereço de texto válido fornecido para geocodificação. Pulando.")
            return StepOutput(content=json.dumps({"error": "address_required"}))

        additional_data["order_state"].address = address
        logger.info(f"Executando geocodificação para o endereço: {address}")
        coords_json = await geocode_address.entrypoint(address=address, tenant_id=self.tenant_id, db=self.db)
        coords = json.loads(coords_json)

        if coords.get("error"):
            raise Exception(f"Erro de geocodificação: {coords.get('error')}")

        additional_data["client_latitude"] = coords.get("lat")
        additional_data["client_longitude"] = coords.get("lng")
        logger.info(f"Geocodificação bem-sucedida. Lat: {coords.get('lat')}, Lng: {coords.get('lng')}")
        return StepOutput(content=f"Coordenadas encontradas para {address}")

    async def _execute_freight_calculation(self, step_input: StepInput) -> StepOutput:
        """Calcula o custo do frete com base nas coordenadas do cliente e da loja."""
        logger.debug(f"ORCHESTRATOR_FLOW: [{self.session_id}] - Entering _execute_freight_calculation")
        additional_data = step_input.additional_data or {}
        order_state: OrderState = additional_data.get("order_state")

        if isinstance(step_input.previous_step_content, str):
            try:
                content_dict = json.loads(step_input.previous_step_content)
                if content_dict.get("error") == "address_required":
                    logger.warning("Cálculo de frete pulado pois o endereço é necessário.")
                    return StepOutput(content=step_input.previous_step_content)
            except (json.JSONDecodeError, TypeError): pass

        client_lat = additional_data.get("client_latitude")
        client_lng = additional_data.get("client_longitude")
        tenant_id = additional_data.get("tenant_id")

        if not all([client_lat, client_lng, tenant_id]):
            logger.warning("Dados insuficientes para calcular o frete.")
            return StepOutput(content=json.dumps({"error": "address_required"}))
        
        freight_result_json = await freight_calculator.entrypoint(
            client_latitude=float(client_lat), client_longitude=float(client_lng),
            tenant_id=tenant_id, db=self.db,
        )
        freight_result = json.loads(freight_result_json)
        if freight_result.get("error"):
            raise Exception(f"Erro na ferramenta de cálculo de frete: {freight_result.get('error')}")

        order_state.freight_details = schemas.FreightDetails(**freight_result)
        logger.info(f"Cálculo de frete bem-sucedido. Detalhes: {freight_result}")
        return StepOutput(content=json.dumps(freight_result))

    async def _pass_through_executor(self, step_input: StepInput) -> StepOutput:
        """Um executor simples que apenas passa o conteúdo do passo anterior adiante."""
        logger.info("ORCHESTRATOR: Executing _pass_through_executor.")
        return StepOutput(content=step_input.previous_step_content)

    async def _handle_file_understanding(
        self, file_content: bytes, mimetype: str
    ) -> tuple[str, Optional[str]]:
        """Processa um arquivo (áudio, imagem) enviado pelo usuário."""
        logger.info(f"[{self.session_id}] - INICIO _handle_file_understanding")
        try:
            agent = get_file_understanding_agent(
                model_id=self.FILE_UNDERSTANDING_MODEL_ID, api_key=self.api_key,
                db=self.db, tenant_id=self.tenant_id,
            )
            prompt = "Analise este arquivo e descreva seu conteúdo. Se for um áudio, transcreva-o."
            media_map = {"audio": Audio, "image": Image, "video": Video}
            media_type_str = mimetype.split("/")[0]

            if media_type_str in media_map:
                media_class = media_map[media_type_str]
                media_input = media_class(content=file_content)
                media_arg = {f"{media_type_str}s": [media_input]}
                response = await agent.arun(prompt, **media_arg)
                if response and response.content and hasattr(response.content, "summary"):
                    return response.content.summary, mimetype

            logger.warning(f"Tipo de arquivo não suportado ou análise falhou: {mimetype}")
            return f"Não foi possível processar o arquivo ({mimetype}).", None
        except Exception as e:
            logger.error(f"Erro na análise do arquivo: {e}", exc_info=True)
            return "Ocorreu um erro ao analisar o arquivo.", None

    async def process_message(
        self, message: str, personality_prompt: str, **kwargs,
    ) -> AIResponse:
        """
        Processa uma nova mensagem do usuário através do workflow completo.
        Este é o principal método público do orquestrador.
        """
        logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 1. Entrando em process_message.")
        order_state = await self._get_order_state()
        logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 2. Estado do pedido recuperado.")

        try:
            file_summary = None
            if kwargs.get("file_content") and kwargs.get("mimetype"):
                logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 3a. Arquivo detectado, processando.")
                summary, file_type = await self._handle_file_understanding(kwargs["file_content"], kwargs["mimetype"])
                message = summary
                file_summary = schemas.FileSummary(summary_text=summary, file_type=file_type) if file_type else None

            if not message or not message.strip():
                logger.warning(f"ORCHESTRATOR_TRACE: [{self.session_id}] - Mensagem vazia, retornando.")
                return AIResponse(response_text="Por favor, envie uma mensagem de texto.")

            additional_data = {
                "original_message": message, "order_state": order_state,
                "personality_prompt": personality_prompt, "tenant_id": self.tenant_id,
                "file_summary": file_summary, "user_id": self.user_id, **kwargs,
            }
            logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 4. Chamando o workflow.arun().")

            workflow_response: WorkflowRunResponse = await self.workflow.arun(
                message=message, additional_data=additional_data
            )
            logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 5. workflow.arun() finalizado.")

            agent_response = workflow_response.content
            final_content = (
                agent_response.content if isinstance(agent_response, RunResponse)
                else agent_response
            )

            if not isinstance(final_content, FinalResponseData):
                logger.warning(f"Conteúdo final inesperado: {final_content}. Encapsulando.")
                final_content = FinalResponseData(text_response=str(final_content))
            
            # <<< INÍCIO DA CORREÇÃO LÓGICA >>>
            # Substitui o placeholder de frete na resposta final.
            response_text = final_content.text_response
            freight_details = final_content.freight_details

            if freight_details and freight_details.cost is not None:
                valor_frete_formatado = f"R$ {freight_details.cost:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                response_text = response_text.replace(
                    "{valor_do_frete}", valor_frete_formatado
                )
            # <<< FIM DA CORREÇÃO LÓGICA >>>

            logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 6. Salvando estado do pedido.")
            await self._save_order_state(order_state)

            logger.info(f"ORCHESTRATOR_TRACE: [{self.session_id}] - 7. FIM process_message, retornando resposta.")
            return AIResponse(
                response_text=response_text,
                human_handoff=final_content.human_handoff_needed,
                send_menu=final_content.send_menu_requested,
                freight_details=final_content.freight_details,
                file_summary=file_summary,
            )
        except Exception as e:
            logger.error(f"Erro crítico no process_message: {e}", exc_info=True)
            return AIResponse(
                response_text=f"Desculpe, ocorreu um erro interno: {e}",
                human_handoff=True,
            )