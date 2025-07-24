import os
import logging
from agno.agent import Agent
from agno.models.google import Gemini
from core.schemas import HumanHandoffOutput

logger = logging.getLogger(__name__)

def get_human_handoff_agent(model_id: str, api_key: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key), # Modelo leve para decisão rápida
        description="Você é um agente especializado em identificar se o usuário deseja falar com um humano ou está frustrado. Responda apenas com um JSON booleano indicando se deve haver handoff.",
        response_model=HumanHandoffOutput,
        structured_outputs=True,
    )
