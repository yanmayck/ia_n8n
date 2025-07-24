import os
import logging
from agno.agent import Agent
from agno.models.google import Gemini
from core.schemas import FileUnderstandingOutput

logger = logging.getLogger(__name__)

def get_file_understanding_agent(model_id: str, api_key: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key), # Modelo mais robusto para análise de mídia
        description="Você é um agente especializado em analisar o conteúdo de arquivos (imagens, áudios, vídeos) e fornecer um resumo conciso. Retorne um JSON com o resumo e o tipo de arquivo.",
        response_model=FileUnderstandingOutput,
        structured_outputs=True,
    )
