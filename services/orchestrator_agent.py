import base64
import os
import logging
import asyncio
import json
from typing import Optional, List, Dict
from datetime import datetime, date

from sqlalchemy.orm import Session 
from starlette.concurrency import run_in_threadpool

from agno.agent import Agent, RunResponse
from agno.models.google import Gemini
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.memory import Memory
from agno.media import Audio, Image, Video
from agno.workflow.v2 import Workflow, Router, Step
from agno.workflow.v2.step import StepInput, StepOutput

from core import schemas
from core.database import DATABASE_URL, SessionLocal
from core.schemas import (
    AIResponse, HumanHandoffOutput, MenuOutput, FreightCalculationOutput,
    FileUnderstandingOutput, GeneralResponseOutput, OrchestratorDecision,
    OrderState, OrderTakingOutput, OrderItem, AnaliseDeIntencao, TarefaIdentificada, FinalResponseData
)
from crud import tenant_crud, product_crud, user_address_crud
from agno.memory.v2.db.postgres import PostgresMemoryDb
from core.vector_db import VectorDBManager
from services.agents.human_handoff_agent import get_human_handoff_agent
from services.agents.menu_agent import get_menu_agent
from services.agents.freight_agent import get_freight_agent
from services.agents.file_understanding_agent import get_file_understanding_agent
from services.agents.general_response_agent import get_general_response_agent
from services.agents.order_taking_agent import get_order_taking_agent
from services.agents.receptionist_agent import get_receptionist_agent # NEW
from services.agents.response_formulation_agent import get_response_formulation_agent # NEW
from services.order_service import save_order_to_database
from services.tools import get_sql_query_tool, get_contextual_suggestions_tool, get_applicable_promotions_tool # Updated
from services.rules_engine import RulesEngine # NEW

logger = logging.getLogger(__name__)

ORDER_STATES: Dict[str, OrderState] = {}
USER_LAST_INTERACTION: Dict[str, datetime] = {}

class OrchestratorAgent:
    async def _route_by_intent(self, step_input: StepInput) -> Step:
        # A intenção já foi identificada pelo 'receptionist_step'
        receptionist_output: AnaliseDeIntencao = step_input.previous_step_content
        
        # Lógica de roteamento baseada na primeira tarefa identificada
        if receptionist_output and receptionist_output.tarefas:
            primeira_tarefa = receptionist_output.tarefas[0].tipo_tarefa
            if primeira_tarefa == 'falar_com_humano':
                return self.human_handoff_step
            elif primeira_tarefa == 'menu':
                return self.menu_step
            elif primeira_tarefa == 'frete':
                return self.freight_step
            elif primeira_tarefa in ['adicionar_item', 'remover_item', 'confirmar_pedido']:
                return self.order_taking_step
        
        # Se nenhuma tarefa específica for identificada, ou for uma pergunta geral
        return self.response_formulation_step

    def __init__(self, db: Session, session_id: str, tenant_id: str, user_id: str):
        logger.debug(f"OrchestratorAgent initialized with session_id={session_id}, tenant_id={tenant_id}, user_id={user_id}")
        self.db = db
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.composite_session_id = f"{user_id}_{tenant_id}"

        # Definir IDs dos modelos de IA
        self.ORCHESTRATOR_MODEL_ID = "models/gemini-2.0-flash-lite"
        self.GENERAL_AGENT_MODEL_ID = "models/gemini-2.0-flash"
        self.ORDER_TAKING_AGENT_MODEL_ID = "models/gemini-2.0-flash"
        self.HUMAN_HANDOFF_MODEL_ID = "models/gemini-2.0-flash-lite"
        self.MENU_AGENT_MODEL_ID = "models/gemini-2.0-flash-lite"
        self.FREIGHT_AGENT_MODEL_ID = "models/gemini-2.0-flash"
        self.FILE_UNDERSTANDING_MODEL_ID = "models/gemini-2.0-flash"
        self.RECEPTIONIST_MODEL_ID = "models/gemini-2.0-flash-lite" # NEW
        self.RESPONSE_FORMULATION_MODEL_ID = "models/gemini-2.0-flash" # NEW

        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")
        
        self.gemini_api_key_2 = os.getenv("GEMINI_API_KEY_2")
        if not self.gemini_api_key_2:
            raise ValueError("A variável de ambiente GEMINI_API_KEY_2 não foi definida.")
        
        self.memory_db = PostgresMemoryDb(table_name="user_memories", db_url=DATABASE_URL)
        self.memory = Memory(db=self.memory_db)
        self.vector_db_manager = VectorDBManager(db=self.db, collection_name=self.tenant_id)

        # Initialize RulesEngine
        self.rules_engine = RulesEngine(self.db) # NEW

        # Initialize Agents
        self.human_handoff_agent = get_human_handoff_agent(model_id=self.HUMAN_HANDOFF_MODEL_ID, api_key=self.gemini_api_key)
        self.menu_agent = get_menu_agent(model_id=self.MENU_AGENT_MODEL_ID, api_key=self.gemini_api_key)
        self.freight_agent = get_freight_agent(model_id=self.FREIGHT_AGENT_MODEL_ID, api_key=self.gemini_api_key_2)
        self.file_understanding_agent = get_file_understanding_agent(model_id=self.FILE_UNDERSTANDING_MODEL_ID, api_key=self.gemini_api_key_2)
        self.order_taking_agent = get_order_taking_agent(model_id=self.ORDER_TAKING_AGENT_MODEL_ID, api_key=self.gemini_api_key_2, memory=self.memory)
        self.receptionist_agent = get_receptionist_agent(model_id=self.RECEPTIONIST_MODEL_ID, api_key=self.gemini_api_key) # NEW
        self.response_formulation_agent = get_response_formulation_agent(model_id=self.RESPONSE_FORMULATION_MODEL_ID, api_key=self.gemini_api_key_2, memory=self.memory)

        # Etapa 1: Criar os Steps
        self.receptionist_step = Step( # NEW
            name="receptionist",
            agent=self.receptionist_agent,
            description="Analisa a mensagem do usuário e identifica as intenções."
        )
        self.human_handoff_step = Step(
            name="human_handoff",
            executor=self._handle_human_handoff_wrapper,
            description="Encaminha a conversa para um atendente humano."
        )
        self.menu_step = Step(
            name="menu",
            executor=self._handle_menu_request_wrapper,
            description="Envia o cardápio para o usuário."
        )
        self.freight_step = Step(
            name="freight",
            executor=self._handle_freight_calculation_wrapper, # Changed to executor
            description="Calcula o frete para o endereço do usuário."
        )
        self.order_taking_step = Step(
            name="order_taking",
            executor=self._handle_order_taking_wrapper,
            description="Anota e gerencia os pedidos do usuário."
        )
        self.response_formulation_step = Step( # NEW
            name="response_formulation",
            executor=self._handle_response_formulation_wrapper,
            description="Formula a resposta final para o usuário."
        )

        # Etapa 2: Construir o Workflow com o Router
        self.workflow = Workflow(
            name="Chatbot Workflow",
            steps=[
                self.receptionist_step, # NEW: Receptionist is the first step
                Router(
                    name="Main Router",
                    selector=self._route_by_intent,
                    choices=[
                        self.human_handoff_step,
                        self.menu_step,
                        self.freight_step,
                        self.order_taking_step,
                        self.response_formulation_step, # NEW: Fallback to response formulation
                    ]
                )
            ]
        )

    async def _get_order_state(self) -> OrderState:
        logger.debug(f"Recuperando estado do pedido para session_id: {self.composite_session_id}")
        return ORDER_STATES.get(self.composite_session_id, OrderState())

    async def _save_order_state(self, state: OrderState):
        logger.debug(f"Salvando estado do pedido para session_id: {self.composite_session_id}: {state.model_dump()}")
        ORDER_STATES[self.composite_session_id] = state

    async def _get_product_price(self, product_name: str) -> float:
        db = SessionLocal()
        try:
            product = await run_in_threadpool(product_crud.get_product_by_name_and_tenant_id, db, name=product_name, tenant_id=self.tenant_id)
            if product and product.price:
                return float(product.price)
            return 0.0
        finally:
            db.close()

    async def process_message(
        self, message: str, personality_prompt: str, file_content: Optional[bytes] = None, mimetype: Optional[str] = None, client_latitude: Optional[float] = None, client_longitude: Optional[float] = None
    ) -> AIResponse:
        logger.debug(f"OrchestratorAgent.process_message iniciado para session_id: {self.composite_session_id}")
        try:
            order_state = await self._get_order_state()
            final_response_data = FinalResponseData(text_response="") # Use o novo schema

            if file_content and mimetype:
                message = await self._handle_file_understanding(file_content, mimetype, final_response_data) or message

            # Se a mensagem estiver vazia após o processamento do arquivo, não há o que fazer.
            if not message.strip():
                return final_response_data.model_dump()

            # Executa o workflow
            workflow_response = await self.workflow.arun(
                message=message,
                additional_data={
                    "final_response_data": final_response_data, # Passa o objeto mutável
                    "order_state": order_state,
                    "client_latitude": client_latitude,
                    "client_longitude": client_longitude,
                    "personality_prompt": personality_prompt,
                    "tenant_id": self.tenant_id # Passa o tenant_id para as ferramentas
                }
            )

            # O workflow agora retorna o FinalResponseData diretamente do response_formulation_step
            run_content = workflow_response.content

            if isinstance(run_content, FinalResponseData):
                final_response_data = run_content
            else:
                # Fallback caso o último step não retorne FinalResponseData
                final_response_data.text_response = str(run_content)

            # Lógica de Saudação: Adiciona apenas na primeira interação do dia e se a resposta não contiver saudação.
            now = datetime.now()
            last_interaction = USER_LAST_INTERACTION.get(self.composite_session_id)
            
            # Verifica se é a primeira interação do dia
            is_first_interaction_today = last_interaction is None or last_interaction.date() < now.date()

            # Verifica se a resposta do agente já contém uma saudação
            response_text_lower = final_response_data.text_response.lower()
            contains_greeting = any(greeting_word in response_text_lower for greeting_word in ["olá", "bem-vindo", "bom dia", "boa tarde", "boa noite"])

            if is_first_interaction_today and not contains_greeting:
                tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, self.db, self.tenant_id)
                nome_loja = tenant.nome_loja if tenant else self.tenant_id
                greeting = f"Olá! Bem-vindo(a) ao Atendente Virtual da {nome_loja}. "
                final_response_data.text_response = greeting + final_response_data.text_response
            
            USER_LAST_INTERACTION[self.composite_session_id] = now

            await self._save_order_state(order_state)
            logger.debug(f"Final response before returning from process_message: {final_response_data.text_response}")
            return schemas.AIResponse(
                response_text=final_response_data.text_response,
                human_handoff=final_response_data.human_handoff_needed,
                send_menu=final_response_data.send_menu_requested,
                freight_details=final_response_data.freight_details,
                file_summary=final_response_data.file_summary
            ).model_dump()
        except Exception as e:
            logger.error(f"Erro no process_message: {e}", exc_info=True)
            raise

    async def _handle_freight_calculation_wrapper(self, step_input: StepInput) -> StepOutput:
        client_latitude = step_input.additional_data.get("client_latitude")
        client_longitude = step_input.additional_data.get("client_longitude")
        tenant_id = step_input.additional_data.get("tenant_id")

        if not client_latitude or not client_longitude:
            # Se não houver coordenadas, o ResponseFormulationAgent pedirá ao usuário.
            return StepOutput(content="Coordenadas do cliente não fornecidas.")

        freight_result = await freight_calculator(client_latitude, client_longitude, tenant_id)
        step_input.additional_data["freight_info"] = freight_result
        
        return StepOutput(content="Frete calculado e armazenado.")

    async def _handle_file_understanding(self, file_content: bytes, mimetype: str, final_response: AIResponse) -> Optional[str]:
        '''
        Processa um arquivo (áudio, imagem, etc.), retorna o texto transcrito se houver,
        ou preenche a resposta final com uma mensagem de erro/status e retorna None.
        '''
        try:
            if not file_content or len(file_content) == 0:
                logger.warning("Arquivo vazio - pulando análise")
                return None

            media_input = None
            prompt = "Analise este arquivo e descreva seu conteúdo. Se for um áudio, transcreva-o."

            if mimetype.startswith("audio/") or mimetype == "audioMessage":
                from agno.media import Audio
                audio_format = "opus" if mimetype == "audioMessage" else mimetype.split('/')[-1]
                media_input = Audio(content=file_content, format=audio_format)
                response = await self.file_understanding_agent.arun(prompt, audio=[media_input])
            elif mimetype.startswith("image/") or mimetype == "imageMessage":
                from agno.media import Image
                media_input = Image(content=file_content)
                response = await self.file_understanding_agent.arun(prompt, images=[media_input])
            elif mimetype.startswith("video/") or mimetype == "videoMessage":
                from agno.media import Video
                media_input = Video(content=file_content)
                response = await self.file_understanding_agent.arun(prompt, videos=[media_input])
            else:
                logger.warning(f"Tipo de arquivo não suportado: {mimetype}")
                final_response.response_text = "Desculpe, não consigo processar este tipo de arquivo."
                return None

            if response and response.content and hasattr(response.content, 'summary'):
                summary_text = response.content.summary
                logger.info(f"Arquivo analisado. Resumo: {summary_text}")
                final_response.file_summary = {"summary_text": summary_text, "file_type": mimetype}
                # Retorna o resumo para ser usado como a nova mensagem
                return summary_text
            else:
                logger.warning("Análise de arquivo não retornou conteúdo ou sumário.")
                final_response.response_text = "Não consegui entender o conteúdo do arquivo. Pode tentar de novo?"
                return None

        except Exception as e:
            logger.error(f"Erro na análise do arquivo: {e}", exc_info=True)
            final_response.response_text = "Ocorreu um erro ao analisar o arquivo. Por favor, tente novamente."
            return None

    def _handle_human_handoff(self, final_response_data: FinalResponseData):
        final_response_data.human_handoff_needed = True
        final_response_data.text_response = "Entendi. Um de nossos atendentes irá continuar a conversa com você em instantes."

    def _handle_menu_request(self, final_response_data: FinalResponseData):
        final_response_data.send_menu_requested = True
        final_response_data.text_response = "Claro! Aqui está o nosso cardápio."

    async def _handle_response_formulation_wrapper(self, step_input: StepInput) -> StepOutput:
        final_response_data = step_input.additional_data.get("final_response_data")
        
        context_for_formulation = {
            "current_message": step_input.message,
            "order_state": step_input.additional_data.get("order_state").model_dump(),
            "promotions_info": step_input.additional_data.get("promotions_info", []),
            "suggestions_info": step_input.additional_data.get("suggestions_info", []),
            "freight_info": step_input.additional_data.get("freight_info"),
            "file_summary": step_input.additional_data.get("file_summary"),
            "human_handoff_requested": final_response_data.human_handoff_needed,
            "send_menu_requested": final_response_data.send_menu_requested,
        }

        response_obj = await self.response_formulation_agent.arun(
            json.dumps(context_for_formulation),
            user_id=self.composite_session_id
        )
        
        # A resposta do agente está em response_obj.content, que é um objeto FinalResponseData.
        # Retornamos isso diretamente para que o workflow possa processá-lo.
        return StepOutput(content=response_obj.content)

    async def _handle_human_handoff_wrapper(self, step_input: StepInput) -> StepOutput:
        final_response_data = step_input.additional_data.get("final_response_data")
        self._handle_human_handoff(final_response_data)
        return StepOutput(content=final_response_data)

    async def _handle_menu_request_wrapper(self, step_input: StepInput) -> StepOutput:
        final_response_data = step_input.additional_data.get("final_response_data")
        self._handle_menu_request(final_response_data)
        return StepOutput(content=final_response_data)

    async def _handle_order_taking_wrapper(self, step_input: StepInput) -> StepOutput:
        order_state = step_input.additional_data.get("order_state")
        message = step_input.message
        tenant_id = step_input.additional_data.get("tenant_id")

        order_output: OrderTakingOutput = (await self.order_taking_agent.arun(message)).content
        
        items_added = False
        if order_output.items:
            order_state.items.extend(order_output.items)
            items_added = True

        if order_output.address:
            order_state.address = order_output.address
            address_schema = schemas.UserAddressCreate(
                user_phone=self.user_id,
                tenant_id=self.tenant_id,
                address_text=order_output.address
            )
            await run_in_threadpool(user_address_crud.create_or_update_user_address, SessionLocal, address=address_schema)

        if order_output.is_final_order and order_state.items:
            order_state.status = "pending_delivery_method"

        # Buscar sugestões e promoções após a tomada de pedido
        if items_added:
            last_product_added_name = order_output.items[-1].product_name
            # Precisamos do ID do produto para buscar sugestões
            product = await run_in_threadpool(product_crud.get_product_by_name_and_tenant_id, SessionLocal, name=last_product_added_name, tenant_id=tenant_id)
            if product:
                suggestions_result = await get_contextual_suggestions_tool(product.id_produto)
                step_input.additional_data["suggestions_info"] = json.loads(suggestions_result)

        promotions_result = await get_applicable_promotions_tool(tenant_id, json.dumps(order_state.model_dump()))
        step_input.additional_data["promotions_info"] = json.loads(promotions_result)

        return StepOutput(content="Pedido processado e sugestões/promoções buscadas.")