import os
import logging
from agno.agent import Agent
from agno.models.google import Gemini
from agno.memory.v2.memory import Memory # Importar Memory
from core.schemas import GeneralResponseOutput
from services.tools import search_tool, product_query_tool # Adicionar product_query_tool
from core.vector_db import VectorDBManager # Importar VectorDBManager

logger = logging.getLogger(__name__)

from typing import Optional, Type
from pydantic import BaseModel

def get_general_response_agent(model_id: str, vector_db_manager: VectorDBManager, memory: Memory, api_key: str, personality_prompt: str, session_id: str, response_model: Type[BaseModel], exponential_backoff: bool = False, retries: int = 0, enable_user_memories: bool = False, enable_session_summaries: bool = False):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key), # Modelo mais robusto para respostas gerais
        description=f"""{personality_prompt}

Você tem uma ferramenta `product_query_tool` para responder a perguntas sobre produtos. Use-a sempre que apropriado.
- Para perguntas sobre o produto mais caro, use `query_type='mais_caro'`.
- Para o mais barato, use `query_type='mais_barato'`.
- Para buscar um produto específico, use `query_type='buscar_por_nome'` e forneça o `product_name`.
- Para listar todos os produtos, use `query_type='listar_todos'`.
""",
        tools=[search_tool, product_query_tool], # Adicionar product_query_tool às ferramentas
        knowledge=[vector_db_manager.knowledge_base], # Adicionar SupabaseKnowledge como conhecimento
        memory=memory, # Passar o objeto de memória
        enable_user_memories=enable_user_memories, # Habilitar memórias do usuário
        response_model=response_model,
        structured_outputs=True,
        session_id=session_id, # Adiciona o ID da sessão para carregar o histórico correto
        exponential_backoff=exponential_backoff,
        retries=retries,
        enable_session_summaries=enable_session_summaries,
    )
    
