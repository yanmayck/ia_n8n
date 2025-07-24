import os
import logging
import asyncio
import json
import re
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from agno.exceptions import ModelProviderError
from agno.media import Audio, Image, Video
from agno.agent import Agent
from agno.models.google import Gemini

from core.database import DATABASE_URL, SessionLocal
from crud import interaction_crud, tenant_crud
from core.schemas import InteractionCreate
from services.orchestrator_agent import OrchestratorAgent
from agno.memory.v2.db.postgres import PostgresMemoryDb

logger = logging.getLogger(__name__)

memory_db = PostgresMemoryDb(table_name="user_memories", db_url=DATABASE_URL)

async def handle_message(
    user_id: str, 
    session_id: str, 
    message: str, 
    tenant_id: str, # Alterado de personality_name
    personality_prompt: str,
    file_content: bytes = None,
    mimetype: str = None,
    client_latitude: float = None,
    client_longitude: float = None
):
    logger.info(f"Iniciando handle_message para session_id: {session_id}")
    db = SessionLocal()
    try:
        # 1. Verificar mensagem duplicada
        is_duplicate = await run_in_threadpool(interaction_crud.get_interaction_by_whatsapp_id, db, whatsapp_message_id=session_id)
        if is_duplicate:
            logger.warning(f"Mensagem duplicada recebida (ID: {session_id}). Ignorando.")
            return {"text": "Mensagem já processada.", "human_handoff": False, "send_menu": False}

        # 2. Obter o tenant
        tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, tenant_id=tenant_id)
        if not tenant:
            raise ValueError("Tenant não encontrado para a personalidade fornecida.")

        # 3. Inicializar e chamar o Orquestrador com os dados brutos
        logger.info(f"Delegando para o OrchestratorAgent. User: {user_id}, Session: {session_id}")
        orchestrator = OrchestratorAgent(
            session_id=session_id,
            tenant_id=tenant.tenant_id,
            user_id=user_id
        )
        
        ai_response_obj = await orchestrator.process_message(
            message=message,
            personality_prompt=personality_prompt,
            file_content=file_content,
            mimetype=mimetype,
            client_latitude=client_latitude,
            client_longitude=client_longitude
        )
        
        ai_response_text = ai_response_obj.response_text
        personality_id = tenant.personality.id if tenant.personality else None

        # 4. Salvar a interação no banco de dados
        new_interaction = InteractionCreate(
            user_phone=user_id,
            whatsapp_message_id=session_id,
            message_from_user=message, # Salva a mensagem original do usuário
            ai_response=ai_response_text,
            personality_id=personality_id,
            tenant_id=tenant.tenant_id # Adicionando o tenant_id que faltava
        )
        await run_in_threadpool(interaction_crud.create_interaction, db, interaction=new_interaction)
        
        return ai_response_obj.model_dump()

    except Exception as e:
        logger.error(f"Erro em handle_message: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Ocorreu um erro interno ao processar a mensagem.")
    finally:
        db.close()
