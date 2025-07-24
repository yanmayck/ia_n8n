import os
import logging
from agno.agent import Agent
from agno.models.google import Gemini
from core.schemas import FreightCalculationOutput
from services.tools import freight_calculator # Importa a ferramenta de cálculo de frete

logger = logging.getLogger(__name__)

def get_freight_agent(model_id: str, api_key: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key), # Pode ser um modelo mais leve
        description="Você é um agente especializado em calcular frete. Se o usuário fornecer um endereço, use a ferramenta 'freight_calculator'. Se não, peça o endereço ou coordenadas. Retorne o resultado do cálculo de frete.",
        tools=[freight_calculator], # Este agente usa a ferramenta de frete
        response_model=FreightCalculationOutput,
        structured_outputs=True,
    )
