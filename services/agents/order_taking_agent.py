import logging
from typing import Optional
from sqlalchemy.orm import Session # Adicionado
from agno.models.google import Gemini
from core.schemas import OrderTakingOutput
from agno.memory.v2.memory import Memory
from services.agents.base_agent import BaseAgent # Nova importação

logger = logging.getLogger(__name__)

def get_order_taking_agent(model_id: str, api_key: str, db: Session, tenant_id: str, user_id: str, session_id: str, memory: Optional[Memory] = None):
    return BaseAgent(
        model=Gemini(id=model_id, api_key=api_key),
        api_key=api_key,
        db=db, tenant_id=tenant_id, user_id=user_id, session_id=session_id,
        description="Você é um agente especializado em identificar os itens de um pedido em uma conversa. Analise o texto e retorne uma lista estruturada de produtos e quantidades.",
        response_model=OrderTakingOutput,
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
