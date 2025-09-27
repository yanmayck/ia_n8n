import logging
import os

from agno.exceptions import ModelProviderError
from agno.memory.v2.db.postgres import PostgresMemoryDb
from core.database import DATABASE_URL  # Removed SessionLocal
from core.schemas import AIResponse, InteractionCreate
from crud import api_key_crud, interaction_crud, tenant_crud
from fastapi import HTTPException
from google.api_core import exceptions as google_exceptions
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from services.main_orchestrator import OrchestratorAgent  # Corrected import

logger = logging.getLogger(__name__)

memory_db = PostgresMemoryDb(table_name="user_memories", db_url=DATABASE_URL)


async def execute_ai_call_with_failover(tenant_id: str, db: Session, orchestrator_call):
    """
    Executa a chamada para a IA (orquestrador) com um sistema de failover de chaves de API.

    Esta função implementa uma lógica de resiliência crucial:
    1.  Tenta usar as chaves de API específicas do tenant, ordenadas por prioridade.
    2.  Se uma chave falhar por limite de uso (`ResourceExhausted`), ela tenta a próxima.
    3.  Se todas as chaves do tenant falharem, ela usa uma chave de API global (do .env) como fallback.
    4.  Se todas as tentativas falharem, levanta uma exceção.

    Args:
        tenant_id (str): O ID do tenant para o qual a chamada está sendo feita.
        db (Session): A sessão do banco de dados para buscar as chaves de API.
        orchestrator_call (Callable): Uma função `async` que recebe a `api_key` como argumento
                                      e executa a lógica principal da IA.

    Returns:
        Any: O resultado da chamada bem-sucedida de `orchestrator_call`.

    Raises:
        HTTPException: Se todas as chaves de API disponíveis falharem.
        ValueError: Se nenhuma chave de API (nem do tenant, nem global) estiver configurada.
    """
    # 1. Tenta buscar chaves específicas do tenant no banco de dados
    logger.info(
        f"CHAT_HANDLER: Buscando chaves de API para o tenant {tenant_id}."
    )  # Corrected log
    api_keys = await run_in_threadpool(
        api_key_crud.get_api_keys_for_tenant, db, tenant_id
    )
    logger.info(
        f"CHAT_HANDLER: Encontradas {len(api_keys)} chaves para o tenant {tenant_id}."
    )  # Corrected log

    # 2. Se houver chaves específicas, usa a lógica de failover entre elas
    if api_keys:
        for key in api_keys:
            if not key.is_active:
                continue
            try:
                logger.info(
                    f"CHAT_HANDLER: Tentando chamada de IA com a chave de prioridade {key.priority} ({key.key_type}) para o tenant {tenant_id}"
                )  # Corrected log
                result = await orchestrator_call(key.api_key_value)
                logger.info(
                    f"CHAT_HANDLER: Chamada de IA com a chave de prioridade {key.priority} bem-sucedida."
                )  # Corrected log
                return result
            except google_exceptions.ResourceExhausted:
                logger.warning(
                    f"Chave de prioridade {key.priority} ({key.key_type}) atingiu o limite. Tentando a próxima."
                )
                continue
            except Exception as e:
                logger.error(
                    f"Erro crítico com a chave de API específica do tenant {key.id}: {e}",
                    exc_info=True,
                )
                raise e  # Levanta a exceção para outros erros

    # 3. Se não houver chaves específicas do tenant, usa a chave global do .env como fallback
    logger.warning(
        f"CHAT_HANDLER: Nenhuma chave de API específica encontrada para o tenant {tenant_id}. Usando a chave global do .env como fallback."
    )  # Corrected log
    global_api_key = os.getenv("GEMINI_API_KEY")
    if not global_api_key:
        raise ValueError(
            f"Nenhuma chave de API específica para o tenant {tenant_id} e nenhuma chave global GEMINI_API_KEY encontrada no .env"
        )

    try:
        logger.info(
            "CHAT_HANDLER: Tentando chamada de IA com a chave global do .env"
        )  # Corrected log
        result = await orchestrator_call(global_api_key)
        logger.info(
            "CHAT_HANDLER: Chamada de IA com a chave global bem-sucedida."
        )  # Corrected log
        return result
    except Exception as e:
        logger.error(
            f"Erro crítico com a chave de API global do .env: {e}", exc_info=True
        )
        raise e

    # 4. Se todas as tentativas (específicas e global) falharem
    raise HTTPException(
        status_code=503,
        detail="Todas as chaves de API disponíveis falharam ou atingiram o limite.",
    )


async def handle_message(
    user_id: str,
    whatsapp_message_id: str,
    message: str,
    tenant_id: str,
    personality_prompt: str,
    db: Session,  # Adicionado db como argumento
    file_content: bytes = None,
    mimetype: str = None,
    client_latitude: float = None,
    client_longitude: float = None,
):
    """
    Ponto de entrada principal para o processamento de mensagens pela IA.

    Esta função é chamada pela rota da API (`/ai`) e orquestra todo o processo:
    1.  Verifica se a mensagem do WhatsApp já foi processada para evitar duplicatas.
    2.  Busca os dados do tenant (loja) no banco de dados.
    3.  Define a chamada para o `OrchestratorAgent`, que contém a lógica principal.
    4.  Invoca `execute_ai_call_with_failover` para executar a chamada de forma resiliente.
    5.  Registra a interação (mensagem do usuário e resposta da IA) no banco de dados.

    Args:
        user_id (str): O identificador do usuário (geralmente o número de telefone).
        whatsapp_message_id (str): O ID único da mensagem do WhatsApp para evitar duplicatas.
        message (str): O texto da mensagem do usuário.
        tenant_id (str): O ID do tenant (loja) que está recebendo a mensagem.
        personality_prompt (str): O prompt de personalidade da IA para guiar o tom da resposta.
        db (Session): A sessão do banco de dados.
        file_content (bytes, optional): Conteúdo de um arquivo (imagem, áudio) em bytes.
        mimetype (str, optional): O tipo MIME do arquivo enviado.
        client_latitude (float, optional): A latitude do cliente, se enviada.
        client_longitude (float, optional): A longitude do cliente, se enviada.

    Returns:
        AIResponse: Um objeto Pydantic contendo a resposta estruturada da IA.

    Raises:
        HTTPException: Se ocorrer um erro durante o processamento.
    """
    logger.info(
        f"HANDLE_MESSAGE_TRACE: Iniciando handle_message para user_id: {user_id}, whatsapp_message_id: {whatsapp_message_id}"
    )
    try:
        # A verificação de duplicados usa o ID da mensagem do WhatsApp
        is_duplicate = await run_in_threadpool(
            interaction_crud.get_interaction_by_whatsapp_id,
            db,
            whatsapp_message_id=whatsapp_message_id,
        )
        if is_duplicate:
            logger.warning(
                f"Mensagem duplicada recebida (ID: {whatsapp_message_id}). Ignorando."
            )
            # Retorna um objeto compatível com a resposta esperada pela API
            return AIResponse(
                response_text="Mensagem já processada.",
                human_handoff=False,
                send_menu=False,
            )

        tenant = await run_in_threadpool(
            tenant_crud.get_tenant_by_id, db, tenant_id=tenant_id
        )
        if not tenant:
            raise ValueError("Tenant não encontrado para a personalidade fornecida.")

        async def orchestrator_call(api_key: str):
            logger.info(
                f"CHAT_HANDLER: Preparando para chamar o OrchestratorAgent com a chave que termina em '...{api_key[-4:]}'."
            )
            # A sessão do orquestrador é baseada no ID do usuário (telefone) para manter o estado
            orchestrator = OrchestratorAgent(
                db=db,
                session_id=user_id,  # MUDANÇA CRÍTICA: A sessão é o usuário
                tenant_id=tenant.tenant_id,
                user_id=user_id,
                api_key=api_key,
            )
            return await orchestrator.process_message(
                message=message,
                personality_prompt=personality_prompt,
                file_content=file_content,
                mimetype=mimetype,
                client_latitude=client_latitude,
                client_longitude=client_longitude,
            )

        ai_response_obj = await execute_ai_call_with_failover(
            tenant_id, db, orchestrator_call
        )

        ai_response_text = ai_response_obj.response_text
        personality_id = tenant.personality.id if tenant.personality else None

        # O registro da interação continua usando o ID único da mensagem do WhatsApp
        new_interaction = InteractionCreate(
            user_phone=user_id,
            whatsapp_message_id=whatsapp_message_id,
            message_from_user=message,
            ai_response=ai_response_text,
            personality_id=personality_id,
            tenant_id=tenant.tenant_id,
        )
        await run_in_threadpool(
            interaction_crud.create_interaction, db, interaction=new_interaction
        )

        return ai_response_obj

    except (ValueError, ModelProviderError) as e:
        logger.error(
            f"Erro de lógica ou provedor de modelo em handle_message: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=400, detail=f"Erro ao processar a mensagem: {str(e)}"
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.critical(f"Erro crítico em handle_message: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Ocorreu um erro interno ao processar a mensagem."
        )
