import os
import logging
import asyncio
import json
import re
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from google.api_core import exceptions as google_exceptions

from agno.exceptions import ModelProviderError

from core.database import DATABASE_URL # Removed SessionLocal
from crud import interaction_crud, tenant_crud, api_key_crud
from core.schemas import InteractionCreate
from services.main_orchestrator import OrchestratorAgent # Corrected import
from agno.memory.v2.db.postgres import PostgresMemoryDb
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

memory_db = PostgresMemoryDb(table_name="user_memories", db_url=DATABASE_URL)

async def execute_ai_call_with_failover(tenant_id: str, db: Session, orchestrator_call):
    # 1. Tenta buscar chaves específicas do tenant no banco de dados
    logger.info(f"CHAT_HANDLER: Buscando chaves de API para o tenant {tenant_id}.") # Corrected log
    api_keys = await run_in_threadpool(api_key_crud.get_api_keys_for_tenant, db, tenant_id)
    logger.info(f"CHAT_HANDLER: Encontradas {len(api_keys)} chaves para o tenant {tenant_id}.") # Corrected log

    # 2. Se houver chaves específicas, usa a lógica de failover entre elas
    if api_keys:
        for key in api_keys:
            if not key.is_active:
                continue
            try:
                logger.info(f"CHAT_HANDLER: Tentando chamada de IA com a chave de prioridade {key.priority} ({key.key_type}) para o tenant {tenant_id}") # Corrected log
                result = await orchestrator_call(key.api_key_value)
                logger.info(f"CHAT_HANDLER: Chamada de IA com a chave de prioridade {key.priority} bem-sucedida.") # Corrected log
                return result
            except google_exceptions.ResourceExhausted as e:
                logger.warning(f"Chave de prioridade {key.priority} ({key.key_type}) atingiu o limite. Tentando a próxima.")
                continue
            except Exception as e:
                logger.error(f"Erro crítico com a chave de API específica do tenant {key.id}: {e}", exc_info=True)
                raise e # Levanta a exceção para outros erros
    
    # 3. Se não houver chaves específicas do tenant, usa a chave global do .env como fallback
    logger.warning(f"CHAT_HANDLER: Nenhuma chave de API específica encontrada para o tenant {tenant_id}. Usando a chave global do .env como fallback.") # Corrected log
    global_api_key = os.getenv("GEMINI_API_KEY")
    if not global_api_key:
        raise ValueError(f"Nenhuma chave de API específica para o tenant {tenant_id} e nenhuma chave global GEMINI_API_KEY encontrada no .env")
    
    try:
        logger.info("CHAT_HANDLER: Tentando chamada de IA com a chave global do .env") # Corrected log
        result = await orchestrator_call(global_api_key)
        logger.info("CHAT_HANDLER: Chamada de IA com a chave global bem-sucedida.") # Corrected log
        return result
    except Exception as e:
        logger.error(f"Erro crítico com a chave de API global do .env: {e}", exc_info=True)
        raise e

    # 4. Se todas as tentativas (específicas e global) falharem
    raise HTTPException(status_code=503, detail="Todas as chaves de API disponíveis falharam ou atingiram o limite.")

async def handle_message( 
    user_id: str, 
    session_id: str, 
    message: str, 
    tenant_id: str, 
    personality_prompt: str,
    db: Session, # Adicionado db como argumento
    file_content: bytes = None,
    mimetype: str = None,
    client_latitude: float = None,
    client_longitude: float = None
):
    logger.info(f"HANDLE_MESSAGE_TRACE: Iniciando handle_message para session_id: {session_id}")
    logger.info(f"HANDLE_MESSAGE_TRACE: Nova sessão de DB criada em handle_message: {db}")
    try:
        is_duplicate = await run_in_threadpool(interaction_crud.get_interaction_by_whatsapp_id, db, whatsapp_message_id=session_id)
        if is_duplicate:
            logger.warning(f"Mensagem duplicada recebida (ID: {session_id}). Ignorando.")
            return {"text": "Mensagem já processada.", "human_handoff": False, "send_menu": False}

        tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, tenant_id=tenant_id)
        if not tenant:
            raise ValueError("Tenant não encontrado para a personalidade fornecida.")

        async def orchestrator_call(api_key: str):
            logger.info(f"CHAT_HANDLER: Preparando para chamar o OrchestratorAgent com a chave que termina em '...{api_key[-4:]}'.")
            orchestrator = OrchestratorAgent(
                db=db,
                session_id=session_id,
                tenant_id=tenant.tenant_id,
                user_id=user_id,
                api_key=api_key
            )
            return await orchestrator.process_message(
                message=message,
                personality_prompt=personality_prompt,
                file_content=file_content,
                mimetype=mimetype,
                client_latitude=client_latitude,
                client_longitude=client_longitude
            )

        ai_response_obj = await execute_ai_call_with_failover(tenant_id, db, orchestrator_call)
        
        ai_response_text = ai_response_obj.response_text
        personality_id = tenant.personality.id if tenant.personality else None

        new_interaction = InteractionCreate(
            user_phone=user_id,
            whatsapp_message_id=session_id,
            message_from_user=message,
            ai_response=ai_response_text,
            personality_id=personality_id,
            tenant_id=tenant.tenant_id
        )
        await run_in_threadpool(interaction_crud.create_interaction, db, interaction=new_interaction)
        
        return ai_response_obj.model_dump()

    except (ValueError, ModelProviderError) as e:
        logger.error(f"Erro de lógica ou provedor de modelo em handle_message: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Erro ao processar a mensagem: {str(e)}")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.critical(f"Erro crítico em handle_message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno ao processar a mensagem.")