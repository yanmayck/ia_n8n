import os
from typing import List, Dict
from dotenv import load_dotenv
import logging

from agno.vectordb.pgvector import PgVector, SearchType
from agno.embedder.google import GeminiEmbedder

load_dotenv()
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

class VectorDBManager:
    def __init__(self, db: Session, collection_name: str):
        self.db = db
        self.collection_name = collection_name
        logger.debug(f"VectorDBManager: Inicializando para a coleção '{self.collection_name}'")
        
        # A DATABASE_URL será obtida da sessão do DB injetada
        # Não é mais necessário carregar de os.getenv aqui

        embedder = GeminiEmbedder(api_key=os.getenv("GEMINI_API_KEY"))
        
        self.knowledge_base = PgVector(
            db_url=str(self.db.connection().engine.url), # Obtém a URL da conexão da sessão
            table_name=self.collection_name,
            embedder=embedder,
            search_type=SearchType.hybrid,
        )
        logger.info(f"PgVector inicializado com sucesso para a tabela: {self.collection_name}")

    def add_documents(self, texts: List[str], metadatas: List[Dict]): # Assinatura corrigida
        logger.info(f"Adicionando {len(texts)} documentos à coleção '{self.collection_name}'...")
        try:
            self.knowledge_base.add_texts(texts=texts, metadatas=metadatas)
            logger.info(f"{len(texts)} documentos adicionados com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao adicionar documentos à coleção '{self.collection_name}': {e}", exc_info=True)
            raise

    def search_documents(self, query: str, k: int = 3) -> List[Dict]:
        logger.debug(f"Buscando na coleção '{self.collection_name}' pela query: '{query}' (top_k={k})")
        try:
            results = self.knowledge_base.query(query=query, top_k=k)
            
            formatted_results = []
            for doc in results:
                formatted_results.append({
                    "page_content": doc.text,
                    "metadata": doc.metadata,
                    "score": doc.score if hasattr(doc, 'score') else None
                })
            logger.debug(f"{len(formatted_results)} resultados encontrados para a query.")
            return formatted_results
        except Exception as e:
            logger.error(f"Erro ao buscar documentos na coleção '{self.collection_name}': {e}", exc_info=True)
            return []
