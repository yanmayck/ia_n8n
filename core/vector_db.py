import os
from typing import List, Dict
from dotenv import load_dotenv
import logging

from agno.vectordb.pgvector import PgVector, SearchType
from agno.embedder.google import GeminiEmbedder
from agno.document.base import Document
from sqlalchemy.orm import Session
from sqlalchemy import exc

load_dotenv()
logger = logging.getLogger(__name__)

class VectorDBManager:
    def __init__(self, db: Session, collection_name: str):
        self.db = db
        self.collection_name = collection_name
        logger.debug(f"VectorDBManager: Inicializando para a coleção '{self.collection_name}'")
        
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        DATABASE_URL = os.getenv("DATABASE_URL")

        if not DATABASE_URL or not GEMINI_API_KEY:
            raise ValueError("Variáveis de ambiente DATABASE_URL e GEMINI_API_KEY devem ser configuradas.")

        embedder = GeminiEmbedder(api_key=GEMINI_API_KEY)
        
        self.vector_db = PgVector(
            db_url=DATABASE_URL,
            table_name=self.collection_name,
            embedder=embedder,
            search_type=SearchType.hybrid,
        )
        logger.info(f"PgVector inicializado com tabela: {self.collection_name}")

    def add_documents(self, texts: List[str], metadatas: List[Dict]):
        logger.info(f"Recriando documentos na coleção '{self.collection_name}'...")
        if not texts:
            return
        
        try:
            # Garante que a tabela e o schema existam antes de qualquer operação
            logger.info(f"Garantindo que a tabela para a coleção '{self.collection_name}' exista.")
            self.vector_db.create()

            # Limpa todos os documentos existentes na coleção do tenant.
            logger.info(f"Limpando todos os documentos antigos da coleção '{self.collection_name}'.")
            self.vector_db.delete()

            # Cria e insere os novos documentos.
            documents_to_insert = []
            for text, metadata in zip(texts, metadatas):
                doc = Document(content=text)
                doc.metadata = metadata
                documents_to_insert.append(doc)
            
            self.vector_db.insert(documents_to_insert)
            logger.info(f"{len(documents_to_insert)} novos documentos inseridos com sucesso.")

        except exc.SQLAlchemyError as e:
            logger.error(f"Erro ao recriar documentos na coleção '{self.collection_name}': {e}", exc_info=True)
            raise

    def search_documents(self, query: str, k: int = 3) -> List[Dict]:
        logger.debug(f"Buscando na coleção '{self.collection_name}' pela query: '{query}' (limit={k})")
        try:
            results = self.vector_db.search(query=query, limit=k)
            
            formatted_results = []
            for doc in results:
                formatted_results.append({
                    "page_content": doc.content,
                    "metadata": doc.meta_data,
                    "score": getattr(doc, 'score', None)
                })
            logger.debug(f"{len(formatted_results)} resultados encontrados para a query.")
            
            # Adicionando logs para inspecionar o conteúdo recuperado
            logger.info(f"VectorDB: Conteúdo recuperado para a query '{query}':")
            for res in formatted_results:
                logger.info(f"  - Page Content: {res['page_content'][:100]}...") # Loga os primeiros 100 caracteres
                logger.info(f"  - Metadata: {res['metadata']}")

            return formatted_results
        except exc.SQLAlchemyError as e:
            logger.error(f"Erro ao buscar documentos na coleção '{self.collection_name}': {e}", exc_info=True)
            return []