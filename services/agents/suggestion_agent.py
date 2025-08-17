import logging
from sqlalchemy.orm import Session
from agno.models.google import Gemini
from services.tools.product import get_contextual_suggestions_tool, get_applicable_promotions_tool
from services.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

def get_suggestion_agent(model_id: str, api_key: str, db: Session, tenant_id: str, user_id: str, session_id: str):
    """
    Cria um agente especializado cuja única função é executar ferramentas
    para coletar sugestões de produtos e promoções aplicáveis.
    """
    return BaseAgent(
        model=Gemini(id=model_id, api_key=api_key),
        api_key=api_key,
        db=db, tenant_id=tenant_id, user_id=user_id, session_id=session_id,
        description="""Você é um assistente de busca de dados. Sua função é usar as ferramentas fornecidas para encontrar sugestões e promoções com base no contexto.""",
        tools=[
            get_contextual_suggestions_tool,
            get_applicable_promotions_tool
        ],
        retries=1,
    )
