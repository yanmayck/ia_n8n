import os
from typing import List, Dict
from dotenv import load_dotenv
import logging

from agno.vectordb.pgvector import PgVector, SearchType
from agno.embedder.google import GeminiEmbedder

load_dotenv()
logger = logging.getLogger(__name__)

class VectorDBManager:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        
        DATABASE_URL = os.getenv("DATABASE_URL")
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

        if not DATABASE_URL or not GEMINI_API_KEY:
            raise ValueError("Variáveis de ambiente DATABASE_URL e GEMINI_API_KEY devem ser configuradas.")

        # O embedder é usado pelo PgVector para criar os embeddings
        embedder = GeminiEmbedder(api_key=GEMINI_API_KEY)
        
        # A instância do PgVector é a nossa base de conhecimento.
        # Ela será passada diretamente para o Agente.
        self.knowledge_base = PgVector(
            db_url=DATABASE_URL,
            table_name=self.collection_name,
            embedder=embedder,
            search_type=SearchType.hybrid,
        )
        logger.info(f"PgVector inicializado com tabela: {self.collection_name}")

    def add_documents(self, documents: List[str], metadatas: List[Dict] = None):
        if not documents:
            return
        
        if metadatas is None:
            metadatas = [{}] * len(documents)
        
        # O método add do PgVector espera uma lista de tuplas (texto, metadados)
        data_to_add = list(zip(documents, metadatas))
        self.knowledge_base.add(data_to_add)
        logger.info(f"{len(data_to_add)} documentos adicionados à tabela {self.collection_name}.")

    def search_documents(self, query: str, k: int = 3) -> List[Dict]:
        results = self.knowledge_base.query(query=query, top_k=k)
        
        formatted_results = []
        for doc in results:
            formatted_results.append({
                "page_content": doc.text,
                "metadata": doc.metadata,
                "score": doc.score if hasattr(doc, 'score') else None
            })
        return formatted_results
