import os
import logging
import pandas as pd
from starlette.concurrency import run_in_threadpool

from agno.agent import Agent
from agno.models.google import Gemini
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.memory import Memory

from agno.knowledge.csv import CSVKnowledgeBase

from core.database import SessionLocal
from crud import tenant_crud, product_crud
from core.schemas import AIResponse
from core.vector_db import VectorDBManager # Importar VectorDBManager

logger = logging.getLogger(__name__)

from core.database import DATABASE_URL

async def load_data_to_vector_db(tenant_id: str, conteudo_loja: str, products_df: pd.DataFrame):
    logger.info(f"Carregando dados para o VectorDBManager do tenant: {tenant_id}")
    db = SessionLocal()
    try:
        vector_db_manager = VectorDBManager(collection_name=tenant_id)

        # Adicionar o conteúdo do arquivo .txt
        documents_to_add = [conteudo_loja]
        metadatas_to_add = [{"tenant_id": tenant_id, "type": "company_info"}]

        # Adicionar os produtos do Excel com formatação aprimorada
        for index, row in products_df.iterrows():
            # Cria um texto descritivo para cada produto
            product_text = (
                f"Produto: {row.get('Plano_(Produto)')}. "
                f"Preço: R$ {str(row.get('Preço_Sugerido_(Mensal)'))}. "
                f"Descrição: {row.get('Principais_Funcionalidades', 'Não informado')}. "
                f"Público-alvo: {row.get('Público-Alvo', 'Não informado')}. "
                f"Observações: {row.get('Limitações/Observações', 'Nenhuma')}."
            )
            documents_to_add.append(product_text)
            
            # Metadados permanecem os mesmos
            metadatas_to_add.append({
                "tenant_id": tenant_id, 
                "type": "product_info", 
                "retrieval_key": row.get('retrieval_key', f"{tenant_id}_{row.get('Plano_(Produto)')}")
            })

        vector_db_manager.add_documents(documents_to_add, metadatas_to_add)
        logger.info(f"Dados do tenant {tenant_id} carregados no Supabase via VectorDBManager.")
    except Exception as e:
        logger.error(f"Erro ao carregar dados para o VectorDBManager do tenant {tenant_id}: {e}", exc_info=True)
        raise
    finally:
        db.close()