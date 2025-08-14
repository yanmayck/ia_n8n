
import logging
from sqlalchemy.orm import Session
from agno.models.google import Gemini
from agno.memory.v2.memory import Memory
from core.schemas import FinalResponseData
from services.tools import get_contextual_suggestions_tool, recommendation_tool, get_applicable_promotions_tool, get_sql_query_tool
from services.agents.base_agent import BaseAgent # Nova importação

logger = logging.getLogger(__name__)

def get_response_formulation_agent(model_id: str, api_key: str, memory: Memory, db: Session, tenant_id: str, user_id: str, session_id: str):
    return BaseAgent(
        model=Gemini(id=model_id, api_key=api_key),
        api_key=api_key,
        db=db, tenant_id=tenant_id, user_id=user_id, session_id=session_id,
        description=(
            """Sua tarefa é formular a resposta final para o usuário, usando as ferramentas disponíveis para encontrar informações se necessário."""
        ),
        tools=[
            get_sql_query_tool, 
            get_contextual_suggestions_tool,
            recommendation_tool,
            get_applicable_promotions_tool
        ],
        instructions=[
            "### REGRAS DE OURO ###",
            "1. **Priorize o Contexto:** Sua resposta DEVE ser baseada PRIMEIRO e ESTRITAMENTE nas informações de contexto fornecidas nos passos anteriores (como 'rag_context' ou 'search_results').",
            "2. **Apresente Ofertas (REGRA INVIOLÁVEL):** Se o contexto contiver uma lista de 'suggestions' ou 'promotions', após confirmar o item do cliente, você DEVE OBRIGATORIAMENTE apresentar essas opções de forma natural e convidativa. Exemplo: 'Ok, anotei seu X-Bacon. Ele fica ótimo com nossa porção de fritas. Deseja incluir?'.",
            "3. **Use Ferramentas como Fallback:** Se a informação não estiver no contexto, use a ferramenta `get_sql_query_tool` para buscar dados específicos. NÃO invente a informação.",
            "4. **NUNCA peça o ID da loja (tenant_id)**. Ele já está disponível para suas ferramentas automaticamente.",
            "5. **Incorpore Detalhes Estruturados:** Se receber detalhes de frete ('freight_details'), SEMPRE inclua o objeto completo e intacto na sua resposta final.",
            "6. **Seja Conciso e Direto:** Formule uma resposta amigável e termine com uma pergunta clara para guiar a conversa.",
            "### REGRAS INVIOLÁVEIS (NUNCA QUEBRE ESTAS REGRAS) ###",
            "- **NUNCA INVENTE INFORMAÇÕES:** Não mencione produtos, preços, ingredientes, promoções ou qualquer outro detalhe que não esteja EXPLICITAMENTE fornecido no contexto ou retornado por uma ferramenta. Se a informação não existe, diga que não a encontrou.",
            "- **NÃO FAÇA PERGUNTAS DESNECESSÁRIAS:** Não peça o endereço do cliente para simplesmente mostrar o cardápio. Responda à pergunta atual com os dados que possui."
        ],
        response_model=FinalResponseData,
        structured_outputs=True,
        memory=memory,
        session_state={"db": db, "tenant_id": tenant_id}, 
        add_state_in_messages=True,  
        enable_user_memories=True,
        enable_session_summaries=True,
        retries=1,
        delay_between_retries=2,
        exponential_backoff=False,
    )