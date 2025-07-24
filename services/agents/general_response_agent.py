import os
import logging
from agno.agent import Agent
from agno.models.google import Gemini
from agno.memory.v2.memory import Memory # Importar Memory
from core.schemas import GeneralResponseOutput
from services.tools import search_tool, product_query_tool # Adicionar product_query_tool
from core.vector_db import VectorDBManager # Importar VectorDBManager

logger = logging.getLogger(__name__)

def get_general_response_agent(model_id: str, vector_db_manager: VectorDBManager, memory: Memory, api_key: str, personality_prompt: str, session_id: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key), # Modelo mais robusto para respostas gerais
        description=personality_prompt, # Usar o prompt dinâmico
        tools=[search_tool, product_query_tool], # Adicionar product_query_tool às ferramentas
        knowledge=[vector_db_manager.knowledge_base], # Adicionar SupabaseKnowledge como conhecimento
        memory=memory, # Passar o objeto de memória
        enable_user_memories=True, # Habilitar memórias do usuário
        response_model=GeneralResponseOutput,
        structured_outputs=True,
        session_id=session_id, # Adiciona o ID da sessão para carregar o histórico correto
    )
    
