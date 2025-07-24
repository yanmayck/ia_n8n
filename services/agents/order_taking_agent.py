import os
import logging
from typing import Optional
from agno.agent import Agent
from agno.models.google import Gemini
from core.schemas import OrderTakingOutput
from agno.memory.v2.memory import Memory

logger = logging.getLogger(__name__)

def get_order_taking_agent(model_id: str, api_key: str, memory: Optional[Memory] = None):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key),
        description="Você é um agente especializado em identificar os itens de um pedido em uma conversa. Analise o texto e retorne uma lista estruturada de produtos e quantidades.",
        response_model=OrderTakingOutput,
        structured_outputs=True,
        memory=memory,
        enable_user_memories=True,
        enable_session_summaries=True,
    )
