import base64
import os
import logging
import asyncio
import json
from typing import Optional, List, Dict
from datetime import datetime, date

from sqlalchemy.orm import Session 
from starlette.concurrency import run_in_threadpool

from agno.agent import Agent
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
    OrderState, OrderTakingOutput, OrderItem
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
from services.order_service import save_order_to_database

logger = logging.getLogger(__name__)

ORDER_STATES: Dict[str, OrderState] = {}
USER_LAST_INTERACTION: Dict[str, datetime] = {}

class OrchestratorAgent:
    def __init__(self, session_id: str, tenant_id: str, user_id: str):
        logger.debug(f"OrchestratorAgent initialized with session_id={session_id}, tenant_id={tenant_id}, user_id={user_id}")
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

        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")
        
        self.gemini_api_key_2 = os.getenv("GEMINI_API_KEY_2")
        if not self.gemini_api_key_2:
            raise ValueError("A variável de ambiente GEMINI_API_KEY_2 não foi definida.")
        
        self.memory_db = PostgresMemoryDb(table_name="user_memories", db_url=DATABASE_URL)
        self.memory = Memory(db=self.memory_db)
        self.vector_db_manager = VectorDBManager(collection_name=self.tenant_id)

        self.orchestrator = Agent(
            model=Gemini(id=self.ORCHESTRATOR_MODEL_ID, api_key=self.gemini_api_key),
            description="Você é um agente orquestrador que delega tarefas a agentes especializados...",
            storage=PostgresStorage(table_name="orchestrator_sessions", db_url=DATABASE_URL),
            add_history_to_messages=True,
            session_id=self.composite_session_id,
            num_history_responses=10,
            response_model=OrchestratorDecision,
        )

        self.human_handoff_agent = get_human_handoff_agent(model_id=self.HUMAN_HANDOFF_MODEL_ID, api_key=self.gemini_api_key)
        self.menu_agent = get_menu_agent(model_id=self.MENU_AGENT_MODEL_ID, api_key=self.gemini_api_key)
        self.freight_agent = get_freight_agent(model_id=self.FREIGHT_AGENT_MODEL_ID, api_key=self.gemini_api_key_2)
        self.file_understanding_agent = get_file_understanding_agent(model_id=self.FILE_UNDERSTANDING_MODEL_ID, api_key=self.gemini_api_key_2)
        self.order_taking_agent = get_order_taking_agent(model_id=self.ORDER_TAKING_AGENT_MODEL_ID, api_key=self.gemini_api_key_2, memory=self.memory)

        # Etapa 1: Criar os Steps
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
            agent=self.freight_agent,
            description="Calcula o frete para o endereço do usuário."
        )
        self.order_taking_step = Step(
            name="order_taking",
            executor=self._handle_order_taking_wrapper,
            description="Anota e gerencia os pedidos do usuário."
        )
        self.general_response_step = Step(
            name="general_response",
            executor=self._handle_general_response_wrapper,
            description="Responde a perguntas gerais e saudações."
        )

        # Etapa 2: Construir o Workflow com o Router
        self.workflow = Workflow(
            name="Chatbot Workflow",
            steps=[
                Router(
                    name="Main Router",
                    selector=self._route_by_context,
                    choices=[
                        self.human_handoff_step,
                        self.menu_step,
                        self.freight_step,
                        self.order_taking_step,
                        self.general_response_step,
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
        db = SessionLocal()
        try:
            order_state = await self._get_order_state()
            final_response = AIResponse(response_text="", human_handoff=False, send_menu=False)

            if file_content and mimetype:
                message = await self._handle_file_understanding(file_content, mimetype, final_response) or message

            if order_state.status.startswith("pending_"):
                return await self._handle_pending_confirmation(db, order_state, message, final_response, client_latitude, client_longitude)

            # Executa o workflow
            workflow_response = await self.workflow.arun(
                message=message,
                additional_data={
                    "final_response": final_response,
                    "order_state": order_state,
                    "client_latitude": client_latitude,
                    "client_longitude": client_longitude,
                    "personality_prompt": personality_prompt,
                    "db": db,
                }
            )

            final_response = workflow_response.content

            # Lógica de Saudação: Adiciona apenas na primeira interação do dia e se a resposta não contiver saudação.
            now = datetime.now()
            last_interaction = USER_LAST_INTERACTION.get(self.composite_session_id)
            
            # Verifica se é a primeira interação do dia
            is_first_interaction_today = last_interaction is None or last_interaction.date() < now.date()

            # Verifica se a resposta do agente já contém uma saudação
            response_text_lower = final_response.response_text.lower()
            contains_greeting = any(greeting_word in response_text_lower for greeting_word in ["olá", "bem-vindo", "bom dia", "boa tarde", "boa noite"])

            if is_first_interaction_today and not contains_greeting:
                tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, self.tenant_id)
                nome_loja = tenant.nome_loja if tenant else self.tenant_id
                greeting = f"Olá! Bem-vindo(a) ao Atendente Virtual da {nome_loja}. "
                final_response.response_text = greeting + final_response.response_text
            
            USER_LAST_INTERACTION[self.composite_session_id] = now

            await self._save_order_state(order_state)
            logger.debug(f"Final response before returning from process_message: {final_response.response_text}")
            return final_response
        finally:
            db.close()

    

    # Adicionando as novas funções auxiliares aqui
    async def _handle_pending_confirmation(self, db: Session, order_state: OrderState, message: str, final_response: AIResponse, client_latitude: Optional[float], client_longitude: Optional[float]):
        user_intent = (await self._get_simple_intent_agent().arun(message)).lower()

        if order_state.status == "pending_delivery_method":
            if "entrega" in user_intent:
                order_state.delivery_method = "entrega"
                saved_address = await run_in_threadpool(user_address_crud.get_user_address, db, user_phone=self.user_id, tenant_id=self.tenant_id)
                if saved_address:
                    order_state.address = saved_address.address_text
                    order_state.status = "pending_address_confirmation"
                    final_response.response_text = f"A entrega será no seu endereço salvo: **{saved_address.address_text}**? (sim/não)"
                else:
                    order_state.status = "pending_address_input"
                    final_response.response_text = "Qual o endereço para a entrega?"
            elif "retirada" in user_intent:
                order_state.delivery_method = "retirada"
                order_state.status = "pending_final_confirmation"
                total_price = sum(await self._get_product_price(item.product_name) * item.quantity for item in order_state.items)
                final_response.response_text = f"Perfeito! O total para retirada é R$ {total_price:.2f}. Posso confirmar o pedido?"
            else:
                final_response.response_text = "Não entendi. Por favor, diga se é para **entrega** ou **retirada**."

        elif order_state.status == "pending_address_confirmation":
            if "sim" in user_intent:
                order_state.status = "pending_final_confirmation"
                # Lógica para calcular frete e apresentar valor final
                # ... (será adicionada)
                final_response.response_text = "Ok, endereço confirmado. Calculando frete..."
            else:
                order_state.status = "pending_address_input"
                final_response.response_text = "Ok. Qual o novo endereço para a entrega?"

        elif order_state.status == "pending_address_input":
            order_state.address = message
            address_schema = schemas.UserAddressCreate(
                user_phone=self.user_id,
                tenant_id=self.tenant_id,
                address_text=message,
                latitude=str(client_latitude) if client_latitude else None,
                longitude=str(client_longitude) if client_longitude else None
            )
            await run_in_threadpool(user_address_crud.create_or_update_user_address, db, address=address_schema)
            order_state.status = "pending_final_confirmation"
            # Lógica para calcular frete e apresentar valor final
            # ... (será adicionada)
            final_response.response_text = f"Endereço salvo: **{message}**. Calculando frete..."

        elif order_state.status == "pending_final_confirmation":
            if "sim" in user_intent:
                order_state.status = "confirmed"
                # Salvar pedido no banco
                # ... (será adicionada)
                final_response.response_text = "Seu pedido foi confirmado e enviado para a preparação! Agradecemos a preferência."
                await self._save_order_state(OrderState()) # Limpa o estado
            else:
                order_state.status = "open"
                final_response.response_text = "Ok, o pedido não foi finalizado. O que você gostaria de fazer?"
        
        return final_response

    def _get_simple_intent_agent(self):
        return Agent(
            model=Gemini(id="models/gemini-2.0-flash-lite", api_key=self.gemini_api_key),
            description="Analise a resposta do usuário e retorne a intenção principal em uma palavra: 'entrega', 'retirada', 'sim', 'não', ou 'outro'."
        )

    def _get_intent_agent(self):
        # Este agente é super simples e focado em apenas uma tarefa.
        return Agent(
            model=Gemini(id="models/gemini-2.0-flash-lite", api_key=self.gemini_api_key),
            description=(
            """Sua única tarefa é classificar a intenção do usuário. Responda com APENAS UMA das seguintes palavras:
            - 'pergunta_produto': Para perguntas sobre produtos, incluindo pedidos para listar, procurar, ou saber qual é o mais caro/barato.
            - 'pedido': Para adicionar itens a um pedido.
            - 'saudacao': Para cumprimentos como 'oi', 'bom dia'.
            - 'despedida': Para despedidas como 'tchau', 'até mais'.
            - 'frete': Para perguntas sobre o custo ou tempo de entrega.
            - 'menu': APENAS quando o usuário pedir explicitamente o 'cardápio' ou 'menu'.
            - 'falar_com_humano': Se o usuário pedir para falar com uma pessoa.
            - 'outro': Para qualquer outra coisa."""
        )
        )
        

    async def _decide_agent_to_call(self, message: str, order_state: OrderState, client_latitude: Optional[float], client_longitude: Optional[float]) -> str:
        # Se a mensagem estiver vazia após a análise do arquivo (ou desde o início), não há o que fazer.
        if not message.strip():
            return "general_response_agent" # Ou alguma outra lógica de fallback

        # Usa o agente de intenção para obter uma classificação clara
        intent_agent = self._get_intent_agent()
        intent_result = await intent_agent.arun(message, user_id=self.composite_session_id)
        intent = intent_result.content.strip().lower()

        logger.info(f"Intenção detectada: '{intent}'")

        # Lógica de decisão explícita baseada na intenção
        if intent == 'falar_com_humano':
            return "human_handoff_agent"
        if intent == 'menu':
            return "menu_agent"
        if intent == 'frete' or (client_latitude and client_longitude):
            return "freight_agent"
        # Se a intenção é sobre produto OU se o usuário já está fazendo um pedido, direciona para o agente geral
        if intent == 'pergunta_produto' or order_state.items:
            return "general_response_agent" # Este agente tem a ferramenta de consulta
        if intent == 'pedido':
            return "order_taking_agent"
        
        # Fallback para o agente geral
        return "general_response_agent"

    async def _handle_order_taking(self, db: Session, order_state: OrderState, message: str, final_response: AIResponse):
        order_output: OrderTakingOutput = (await self.order_taking_agent.arun(message)).content
        
        if order_output.items:
            order_state.items.extend(order_output.items)
            items_added_text = ", ".join([f"{item.quantity}x {item.product_name}" for item in order_output.items])
            final_response.response_text = f"Anotei: {items_added_text}. Deseja mais alguma coisa?"

        if order_output.address:
            order_state.address = order_output.address
            # Salva o endereço para uso futuro
            address_schema = schemas.UserAddressCreate(
                user_phone=self.user_id,
                tenant_id=self.tenant_id,
                address_text=order_output.address
            )
            await run_in_threadpool(user_address_crud.create_or_update_user_address, db, address=address_schema)
            final_response.response_text = "Endereço de entrega atualizado. Deseja mais alguma coisa?"

        if order_output.is_final_order and order_state.items:
            order_state.status = "pending_delivery_method"
            final_response.response_text = "Ótimo! Você prefere que seja para **entrega** ou para **retirada na loja**?"

    async def _handle_freight_calculation(self, client_latitude: Optional[float], client_longitude: Optional[float], final_response: AIResponse):
        if not client_latitude or not client_longitude:
            final_response.response_text = "Para calcular o frete, por favor, compartilhe sua localização ou digite seu endereço."
            return

        # Etapa 1: Chamar o agente especialista para obter os dados brutos.
        prompt_para_calculo = f"Calcular frete para latitude {client_latitude}, longitude {client_longitude}, e tenant_id {self.tenant_id}"
        freight_result_obj = await self.freight_agent.arun(prompt_para_calculo)
        freight_result = freight_result_obj.content

        # Etapa 2: Verificar o resultado e passar para o agente de resposta geral formular a frase.
        if isinstance(freight_result, schemas.FreightCalculationOutput):
            # Criar um prompt para o agente de resposta geral com o contexto e os dados.
            prompt_para_resposta = (
                f"O usuário pediu para calcular o frete. A ferramenta retornou os seguintes dados: "
                f"{freight_result.model_dump_json()}. Com base nisso, formule uma resposta amigável e natural."
            )
            
            # Chamar o agente de resposta geral para criar a frase.
            resposta_geral_obj = await self.general_response_agent.arun(prompt_para_resposta, user_id=self.composite_session_id)
            final_response.response_text = resposta_geral_obj.content.text_response
            final_response.freight_details = freight_result.model_dump()
        else:
            # Se a ferramenta retornar uma string de erro, apenas a repasse.
            final_response.response_text = str(freight_result)

    

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

    def _handle_human_handoff(self, final_response: AIResponse):
        final_response.human_handoff = True
        final_response.response_text = "Entendi. Um de nossos atendentes irá continuar a conversa com você em instantes."

    def _handle_menu_request(self, final_response: AIResponse):
        final_response.send_menu = True
        final_response.response_text = "Claro! Aqui está o nosso cardápio."

    async def _handle_general_response(self, message: str, personality_prompt: str, final_response: AIResponse):
        db = SessionLocal()
        try:
            tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, self.tenant_id)
            nome_loja = tenant.nome_loja if tenant else self.tenant_id
        finally:
            db.close()

        general_response_agent = get_general_response_agent(
            model_id=self.GENERAL_AGENT_MODEL_ID,
            vector_db_manager=self.vector_db_manager,
            memory=self.memory,
            api_key=self.gemini_api_key_2,
            personality_prompt=personality_prompt,
            session_id=self.composite_session_id,
            response_model=GeneralResponseOutput,
            exponential_backoff=True,
            retries=3,
            enable_user_memories=True,
            enable_session_summaries=True
        )

        prompt_com_regras = message

        logger.debug(f"Enviando prompt com regras para o Agente Geral: {prompt_com_regras}")

        general_output = await general_response_agent.arun(prompt_com_regras, user_id=self.composite_session_id)

        logger.debug(f"Resposta bruta do Agente Geral: {general_output}")

        if general_output and general_output.content and hasattr(general_output.content, 'text_response'):
            final_response.response_text = general_output.content.text_response
        else:
            logger.error(f"O Agente Geral não retornou uma resposta válida. Saída recebida: {general_output}")
            final_response.response_text = "Desculpe, não consegui processar sua solicitação no momento. Tente novamente."

    async def _route_by_context(self, step_input: StepInput) -> List[Step]:
        """Decide qual Step executar com base no contexto."""
        additional_data = step_input.additional_data or {}
        message = step_input.message
        order_state = additional_data.get("order_state")
        client_latitude = additional_data.get("client_latitude")
        client_longitude = additional_data.get("client_longitude")

        agent_name = await self._decide_agent_to_call(
            message, order_state, client_latitude, client_longitude
        )

        logger.info(f"Router decidiu chamar: '{agent_name}'")

        if agent_name == "human_handoff_agent":
            return [self.human_handoff_step]
        if agent_name == "menu_agent":
            return [self.menu_step]
        if agent_name == "freight_agent":
            return [self.freight_step]
        if agent_name == "order_taking_agent":
            return [self.order_taking_step]
        
        return [self.general_response_step]

    async def _handle_human_handoff_wrapper(self, step_input: StepInput) -> StepOutput:
        final_response = step_input.additional_data.get("final_response")
        self._handle_human_handoff(final_response)
        return StepOutput(content=final_response)

    async def _handle_menu_request_wrapper(self, step_input: StepInput) -> StepOutput:
        final_response = step_input.additional_data.get("final_response")
        self._handle_menu_request(final_response)
        return StepOutput(content=final_response)

    async def _handle_general_response_wrapper(self, step_input: StepInput) -> StepOutput:
        final_response = step_input.additional_data.get("final_response")
        message = step_input.message
        personality_prompt = step_input.additional_data.get("personality_prompt")
        await self._handle_general_response(message, personality_prompt, final_response)
        return StepOutput(content=final_response)

    async def _handle_order_taking_wrapper(self, step_input: StepInput) -> StepOutput:
        final_response = step_input.additional_data.get("final_response")
        db = step_input.additional_data.get("db")
        order_state = step_input.additional_data.get("order_state")
        message = step_input.message
        await self._handle_order_taking(db, order_state, message, final_response)
        return StepOutput(content=final_response)

        
