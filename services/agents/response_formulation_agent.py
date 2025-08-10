import logging
from sqlalchemy.orm import Session
from agno.agent import Agent
from agno.models.google import Gemini
from agno.memory.v2.memory import Memory
from core.schemas import FinalResponseData
# Adicionando a importação da ferramenta SQL
from services.tools import get_contextual_suggestions_tool, recommendation_tool, get_applicable_promotions_tool, get_sql_query_tool

logger = logging.getLogger(__name__)

def get_response_formulation_agent(model_id: str, api_key: str, memory: Memory, db: Session, tenant_id: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key),
        description=(
            """Sua tarefa é formular a resposta final para o usuário, usando as ferramentas disponíveis para encontrar informações se necessário."""
        ),
        # Adicionando a ferramenta de SQL e as instruções de uso
        tools=[
            get_sql_query_tool, # Ferramenta para buscar informações gerais
            get_contextual_suggestions_tool,
            recommendation_tool,
            get_applicable_promotions_tool
        ],
        instructions=[
            "### REGRAS DE OURO ###",
            "1. **Priorize o Contexto:** Baseie sua resposta PRIMEIRO nas informações de contexto fornecidas pelos passos anteriores (como 'rag_context' ou 'search_results').",
            "2. **Use Ferramentas como Fallback:** Se a resposta não estiver no contexto, use a ferramenta `get_sql_query_tool` para buscar informações específicas sobre produtos, promoções ou opcionais.",
            "3. **NUNCA peça o ID da loja (tenant_id)**. Ele já está disponível para suas ferramentas automaticamente.",
            "4. **Incorpore Detalhes Estruturados:** Se receber detalhes de frete ('freight_details'), SEMPRE inclua o objeto completo e intacto na sua resposta final.",
            "5. **Seja Conciso e Direto:** Formule uma resposta amigável e termine com uma pergunta clara para guiar a conversa."
        ],
        response_model=FinalResponseData,
        structured_outputs=True,
        memory=memory,
        session_state={"db": db, "tenant_id": tenant_id}, # <-- tenant_id injetado aqui
        add_state_in_messages=True,  # <-- ESSENCIAL: Injeta o tenant_id no prompt
        enable_user_memories=True,
        enable_session_summaries=True,
        retries=1,
        delay_between_retries=2,
        exponential_backoff=False,
    )
