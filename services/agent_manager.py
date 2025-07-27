import os
import logging
from starlette.concurrency import run_in_threadpool

from core.database import SessionLocal
from crud import tenant_crud
from core.vector_db import VectorDBManager

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

async def load_data_to_vector_db(db: Session, tenant_id: str):
    logger.info(f"Iniciando carregamento de dados para o VectorDB do tenant: {tenant_id}")
    db = SessionLocal()
    try:
        vector_db_manager = VectorDBManager(db, collection_name=tenant_id)

        tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, tenant_id)

        if not tenant or not tenant.config_ai:
            logger.warning(f"Nenhuma informação de loja (config_ai) encontrada para o tenant {tenant_id}. O VectorDB não será atualizado.")
            return

        # Prepara o texto e os metadados separadamente
        texts = [tenant.config_ai]
        metadatas = [{"source": "store_info", "tenant_id": tenant_id}]

        logger.info(f"Preparando para adicionar/atualizar o documento de informações da loja no VectorDB.")
        await run_in_threadpool(vector_db_manager.add_documents, texts, metadatas)
        
        logger.info(f"Documento de informações da loja carregado/atualizado com sucesso no VectorDB para o tenant {tenant_id}.")

    except Exception as e:
        logger.error(f"Erro CRÍTICO ao carregar dados para o VectorDB do tenant {tenant_id}: {e}", exc_info=True)
        raise
    finally:
        db.close()
