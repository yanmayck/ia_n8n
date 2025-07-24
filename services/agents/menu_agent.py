import os
import logging
from agno.agent import Agent
from agno.models.google import Gemini
from core.schemas import MenuOutput

logger = logging.getLogger(__name__)

def get_menu_agent(model_id: str, api_key: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key), # Modelo leve para decisão rápida
        description="Você é um agente especializado em identificar se o usuário pediu o cardápio. Responda apenas com um JSON booleano indicando se o cardápio deve ser enviado.",
        response_model=MenuOutput,
        structured_outputs=True,
    )
