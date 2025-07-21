import os
import logging
from fastapi import HTTPException
import httpx

# Frameworks de IA
from agno.agent import Agent
from agno.tools import tool
from agno.models.google import Gemini
from duckduckgo_search import DDGS
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.memory import Memory
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.exceptions import ModelProviderError
import psycopg2
from dotenv import load_dotenv
import json

# Módulos locais
from core.database import SessionLocal
from crud import crud
from core.models import Interaction
from core.schemas import InteractionCreate, AIResponse
import langchain
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
import pandas as pd
import asyncio
from starlette.concurrency import run_in_threadpool
from agno.media import Audio, Image, Video
from agno.knowledge import AgentKnowledge
from agno.knowledge.csv import CSVKnowledgeBase
from agno.vectordb.chroma import ChromaDb
from agno.embedder.google import GeminiEmbedder

# --- Configuração do Cache do LangChain ---
# Inicializa o cache usando um banco de dados SQLite para armazenar os resultados
# das chamadas ao LLM, evitando repetições e acelerando respostas.
set_llm_cache(SQLiteCache(database_path="langchain.db"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Monta a URL do banco de dados para a Agno ---
# Carrega as variáveis de ambiente
load_dotenv()
DB_USER = os.getenv("POSTGRES_USER")
SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("POSTGRES_DB")

# Garante que todas as variáveis necessárias estão presentes
if not all([DB_USER, SUPABASE_PROJECT_REF, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise ValueError("Uma ou mais variáveis de ambiente do banco de dados não estão configuradas.")

# Formata a URL corretamente para o PostgresStorage da Agno
DB_URL = f"postgresql+psycopg2://{DB_USER}.{SUPABASE_PROJECT_REF}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Ferramentas de IA com o decorador @tool ---

# A FERRAMENTA company_info_search FOI REMOVIDA, POIS SERÁ SUBSTITUÍDA PELA KNOWLEDGE BASE.

@tool
def search_tool(query: str) -> str:
    """Use esta ferramenta para realizar uma pesquisa na web usando DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return str(results) if results else "Nenhum resultado encontrado."
    except Exception as e:
        logger.error(f"Erro na ferramenta de busca: {e}")
        return "Ocorreu um erro ao tentar pesquisar na web."

# A ferramenta image_generator foi removida.

# --- Configuração do Agente de IA ---

async def get_agent(personality_prompt: str, session_id: str, tenant_id: str):
    """Cria e configura um agente Agno com base na personalidade e no histórico."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")

    knowledge_bases = []
    db_session = SessionLocal()
    temp_files_to_delete = []
    tenant = None

    try:
        # 1. Obter dados do tenant
        tenant = await run_in_threadpool(crud.get_tenant_by_id, db_session, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant com ID {tenant_id} não encontrado.")
        
        products = await run_in_threadpool(crud.get_products_by_tenant_id, db_session, tenant_id)
        products_df = pd.DataFrame([p.__dict__ for p in products])

        # 2. Configurar o Embedder e o VectorDB corretamente
        gemini_embedder = GeminiEmbedder(
            api_key=gemini_api_key
            # O parâmetro 'model' foi removido para compatibilidade com a versão instalada.
        )
        db_path = f"./chroma_db/{tenant_id}"
        vector_db = ChromaDb(
            collection=f"tenant_{tenant_id}",
            path=db_path,
            embedder=gemini_embedder # Passando o embedder do Agno
        )

        # 3. Preparar as bases de conhecimento (KBs)
        knowledge_bases = []
        if tenant.config_ai:
            config_csv_path = f"temp_{tenant_id}_config.csv"
            pd.DataFrame([{'info': tenant.config_ai}]).to_csv(config_csv_path, index=False)
            temp_files_to_delete.append(config_csv_path)
            knowledge_bases.append(CSVKnowledgeBase(
                path=config_csv_path,
                vector_db=vector_db,
                page_content_column="info",
                description="Informações gerais sobre a empresa."
            ))

        if not products_df.empty:
            products_csv_path = f"temp_{tenant_id}_products.csv"
            products_df.to_csv(products_csv_path, index=False)
            temp_files_to_delete.append(products_csv_path)
            knowledge_bases.append(CSVKnowledgeBase(
                path=products_csv_path,
                vector_db=vector_db,
                page_content_column="name",
                description="Informações sobre os produtos e cardápio."
            ))

        # 4. Carregar os dados em cada KB individualmente
        if knowledge_bases:
            logger.info(f"Encontradas {len(knowledge_bases)} bases de conhecimento para carregar.")
            for kb in knowledge_bases:
                kb.load()
            logger.info("Bases de conhecimento carregadas com sucesso.")

    finally:
        db_session.close()
        for f_path in temp_files_to_delete:
            if os.path.exists(f_path):
                os.remove(f_path)

    # Regras para o envio do cardápio
    menu_rules = f"""
Regras estritas para o cardápio e mídia:
1.  Quando o usuário pedir o cardápio (ex: "me manda o cardápio", "qual o cardápio?"), sua ÚNICA ação deve ser:
    - Responder com um texto curto e amigável (ex: "Com certeza! 😊 Aqui está o nosso cardápio:").
    - Definir 'send_menu' como 'True' para que o sistema envie a IMAGEM do cardápio.
    - NUNCA liste os itens do cardápio em formato de texto. O cardápio é a imagem.
2.  Nunca envie o cardápio sem ser solicitado. Em vez disso, sempre que for relevante, pergunte se o usuário gostaria de vê-lo.
3.  Se o histórico da conversa estiver vazio, esta é a primeira interação. Sua resposta DEVE ser EXATAMENTE: "Olá! Bem-vindo(a) ao Atendente Virtual da {tenant.nome_loja}. 😊 Podemos começar o seu pedido? Se desejar, posso te mostrar o cardápio. 🍔" e 'send_menu' DEVE ser 'False'.
4. Ignore qualquer imagem, áudio ou vídeo que o usuário enviar se não for diretamente relevante para um pedido ou pergunta. Não comente sobre a mídia, apenas foque na parte de texto da mensagem do usuário.
"""

    # Configuração da Memória
    memory_db = SqliteMemoryDb(
        table_name="user_memories",
        db_file=f"memory_{tenant_id}.db"
    )
    memory = Memory(db=memory_db)


    # Configuração final do Agente
    full_prompt = f"{personality_prompt}\n{menu_rules}\nUse a base de conhecimento para responder a perguntas sobre a empresa."

    return Agent(
        model=Gemini(id="gemini-2.0-flash-lite", api_key=gemini_api_key), # Modelo atualizado para a versão Lite
        tools=[search_tool], # Removido image_generator da lista
        description=full_prompt,
        knowledge=knowledge_bases,
        show_tool_calls=True,
        storage=PostgresStorage(table_name="agent_sessions", db_url=DB_URL),
        memory=memory,
        enable_user_memories=True,
        add_history_to_messages=True,
        session_id=session_id,
        num_history_responses=5,
        response_model=AIResponse,
    )

# --- Lógica de Mensagens e Histórico ---

async def handle_message(
    user_id: str, 
    session_id: str, 
    message: str, 
    personality_name: str, 
    personality_prompt: str,
    file_content: bytes = None,
    mimetype: str = None
):
    """
    Processa a mensagem, incluindo mídias (áudio, imagem, vídeo), usando uma 
    abordagem de múltiplos passos para pré-processamento de mídia.
    """
    db = SessionLocal()
    try:
        is_duplicate = await run_in_threadpool(crud.get_interaction_by_whatsapp_id, db, whatsapp_message_id=session_id)
        if is_duplicate:
            logger.warning(f"Mensagem duplicada recebida (ID: {session_id}). Ignorando.")
            return {"text": "Mensagem já processada.", "human_handoff": False, "send_menu": False}

        # --- FASE 1: PRÉ-PROCESSAMENTO DE MÍDIA ---
        media_summary = ""
        if file_content and mimetype:
            if 'audio' in mimetype:
                logger.info("Fase 1: Detectado áudio. Iniciando agente de transcrição.")
                transcriber_agent = Agent(
                    model=Gemini(id="gemini-2.0-flash-lite", api_key=os.getenv("GEMINI_API_KEY")), # Modelo atualizado para a versão Lite
                    description="Sua única tarefa é transcrever o áudio fornecido com a maior precisão possível."
                )
                response = await transcriber_agent.arun("", audio=[Audio(content=file_content)])
                media_summary = f"(áudio transcrito: {response.content})"
                logger.info(f"Fase 1: Áudio transcrito com sucesso: '{response.content}'")

            elif 'video' in mimetype:
                logger.info("Fase 1: Detectado vídeo. Iniciando agente de análise de vídeo.")
                video_analyzer_agent = Agent(
                    model=Gemini(id="gemini-2.0-flash-lite", api_key=os.getenv("GEMINI_API_KEY")), # Modelo atualizado para a versão Lite
                    description="Sua única tarefa é descrever o conteúdo do vídeo fornecido de forma concisa e objetiva."
                )
                response = await video_analyzer_agent.arun("", videos=[Video(content=file_content)])
                media_summary = f"(resumo do vídeo: {response.content})"
                logger.info(f"Fase 1: Vídeo analisado com sucesso: '{response.content}'")

        final_message_for_agent = f"{message} {media_summary}".strip()
        
        # --- FASE 2: CONVERSA ---
        logger.info(f"Fase 2: Enviando para o agente de conversa: '{final_message_for_agent}'")
        tenant = await run_in_threadpool(crud.get_tenant_by_personality_name, db, personality_name=personality_name)
        if not tenant:
            raise ValueError("Tenant não encontrado para a personalidade fornecida.")

        assistant = await get_agent(
            personality_prompt=personality_prompt, 
            session_id=session_id,
            tenant_id=tenant.tenant_id 
        )
        
        # Passa a mensagem final (com possível transcrição) e a imagem (se houver)
        media_kwargs = {}
        if mimetype and 'image' in mimetype and file_content:
            media_kwargs['images'] = [Image(content=file_content)]

        max_retries = 3
        retry_delay = 2  # segundos

        for attempt in range(max_retries):
            try:
                logger.info(f"Tentativa {attempt + 1}/{max_retries} de chamar o modelo Gemini.")
                ai_response_obj = (await assistant.arun(final_message_for_agent, user_id=user_id, **media_kwargs)).content
                
                # Se a chamada for bem-sucedida, retorna o resultado
                personality_id = tenant.personality.id if tenant.personality else None
                new_interaction = InteractionCreate(
                    user_phone=user_id,
                    whatsapp_message_id=session_id,
                    message_from_user=message,
                    ai_response=ai_response_obj.response_text,
                    personality_id=personality_id
                )
                await run_in_threadpool(crud.create_interaction, db, interaction=new_interaction)
                return ai_response_obj.model_dump()

            except ModelProviderError as e:
                logger.warning(f"Erro do provedor do modelo (tentativa {attempt + 1}/{max_retries}): {e}")
                if "503" in str(e) and attempt < max_retries - 1:
                    logger.info(f"Modelo sobrecarregado. Tentando novamente em {retry_delay} segundos...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("Máximo de tentativas atingido ou erro não recuperável.")
                    # Lança uma exceção HTTP específica para o erro 503
                    raise HTTPException(status_code=503, detail="O serviço de IA está indisponível no momento. Tente novamente mais tarde.")

    except Exception as e:
        logger.error(f"Erro em handle_message: {e}", exc_info=True)
        # Se for uma HTTPException já tratada, apenas a relança
        if isinstance(e, HTTPException):
            raise e
        # Para outros erros, lança um 500 genérico
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno ao processar a mensagem.")
    finally:
        db.close()
    