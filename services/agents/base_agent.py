import logging
import asyncio
import json
from typing import List, Dict, Optional

from agno.agent import Agent
from core.database import DATABASE_URL 
from core.vector_db import VectorDBManager 
from sqlalchemy.orm import Session 
from starlette.concurrency import run_in_threadpool 

logger = logging.getLogger(__name__)

class BaseAgent(Agent):
    def __init__(self, model, api_key: str, db: Session, tenant_id: str, user_id: str, session_id: str, **kwargs):
        super().__init__(
            model=model,
            api_key=api_key, 
            **kwargs
        )
        
        self.conversational_memory_db_manager = VectorDBManager(db=db, collection_name=f"conv_memory_{tenant_id}")

        self.db = db 
        self.tenant_id = tenant_id 
        self.user_id = user_id 
        self.session_id = session_id 

    async def store_conversation_memory(self, text_to_store: str, memory_type: str, metadata: Optional[Dict] = None):
        """
        Armazena um pedaço de memória conversacional no banco de dados vetorial.
        text_to_store: O texto a ser armazenado (ex: mensagem do usuário, resumo da IA).
        memory_type: Tipo de memória (ex: "user_message", "ai_response", "summary", "fact").
        metadata: Metadados adicionais para filtragem (ex: {"user_id": "...", "session_id": "..."}).
        """
        default_metadata = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "type": memory_type
        }
        final_metadata = {**default_metadata, **(metadata or {})}
        
        await run_in_threadpool(
            self.conversational_memory_db_manager.add_documents,
            texts=[text_to_store],
            metadatas=[final_metadata]
        )
        logger.info(f"Memória conversacional armazenada: {memory_type} para sessão {self.session_id}")

    async def retrieve_relevant_memories(self, query: str, k: int = 5) -> List[Dict]:
        """
        Recupera memórias conversacionais relevantes do banco de dados vetorial.
        query: A query de busca (geralmente a mensagem atual do usuário).
        k: Número de memórias mais relevantes a serem recuperadas.
        """
        logger.info(f"Recuperando memórias relevantes para a query: \'{query}\' (k={k})")
        
        results = await run_in_threadpool(
            self.conversational_memory_db_manager.search_documents,
            query=query,
            k=k
        )
        
        filtered_results = [
            r for r in results
            if r['metadata'].get('user_id') == self.user_id
        ]
        
        logger.info(f"Recuperadas {len(filtered_results)} memórias relevantes.")
        return filtered_results
