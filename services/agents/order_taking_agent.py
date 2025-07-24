import os
import logging
from agno.agent import Agent
from agno.models.google import Gemini
from core.schemas import OrderTakingOutput

logger = logging.getLogger(__name__)

def get_order_taking_agent(model_id: str, api_key: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key),
        description="Você é um agente especializado em identificar os itens de um pedido em uma conversa. Analise o texto e retorne uma lista estruturada de produtos e quantidades.",
        response_model=OrderTakingOutput,
        structured_outputs=True,
    )
