
import logging
from sqlalchemy.orm import Session
from agno.models.google import Gemini
from agno.memory.v2.memory import Memory
from core.schemas import FinalResponseData
from services.tools.product import get_contextual_suggestions_tool, recommendation_tool, get_applicable_promotions_tool
from services.tools.sql import get_sql_query_tool
from services.agents.base_agent import BaseAgent # Nova importação

logger = logging.getLogger(__name__)

def get_response_formulation_agent(model_id: str, api_key: str, memory: Memory, db: Session, tenant_id: str, user_id: str, session_id: str):
    return BaseAgent(
        model=Gemini(id=model_id, api_key=api_key, temperature=0.2),
        api_key=api_key,
        db=db, tenant_id=tenant_id, user_id=user_id, session_id=session_id,
                description=(
            """Sua tarefa é formular a resposta final para o usuário, usando as ferramentas disponíveis para encontrar informações se necessário."""
        ),
        tools=[],
        instructions=[
            "### REGRAS DE OURO ###",
            "1. **FOCO NA AÇÃO REALIZADA:** Se o contexto contiver 'Contexto da Ação Realizada', sua resposta DEVE ser uma confirmação direta e amigável dessa ação. Ex: se o contexto for 'Item X removido', responda 'Ok, item X removido do seu pedido.'. NÃO adicione promoções ou sugestões nesse momento.",
            "2. **PRIORIZE O CONTEXTO!** Se um contexto como 'rag_context', 'search_results', ou 'freight_details' for fornecido (e não houver um 'Contexto da Ação Realizada'), sua resposta DEVE ser baseada **EXCLUSIVAMENTE** nele.",
            "3. **VENDA PROATIVA (SOMENTE APÓS ADIÇÃO):** Se o contexto contiver uma lista de 'sugestoes' ou 'promocoes' E a ação foi de adicionar um item, você DEVE apresentar essas opções de forma natural.",
            "4. **Seja um Porta-Voz, Não um Cérebro:** Sua função é apenas formatar os dados recebidos em uma frase amigável. A lógica e os dados já foram definidos pelos passos anteriores.",
            "### ROLE AND GOAL ###",
            "You are a helpful and friendly customer service assistant. Your goal is to generate natural-sounding sentences based on the user's request and the context provided.",
            "### CRITICAL RULE: FREIGHT ANNOUNCEMENT ###",
            "If you see 'freight_details' in the context, it means the shipping cost has been calculated. Your response MUST be a single, complete sentence that includes the exact placeholder {valor_do_frete}.",
            "You have creative freedom on the sentence structure, but it MUST include the placeholder.",
            "### EXAMPLES OF GOOD RESPONSES (for freight context) ###",
            '- "Claro! O valor da entrega para seu endereço fica em {valor_do_frete}. Podemos confirmar?".',
            '- "Ok, o frete fica {valor_do_frete}. Deseja adicionar mais alguma coisa?".',
            '- "Prontinho! O custo do frete é {valor_do_frete}."'
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