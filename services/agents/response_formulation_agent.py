import logging
from agno.agent import Agent
from agno.models.google import Gemini
from agno.memory.v2.memory import Memory
from core.schemas import FinalResponseData # Assuming this schema will be created/updated

logger = logging.getLogger(__name__)

def get_response_formulation_agent(model_id: str, api_key: str, memory: Memory):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key),
        description="""
        Você é um assistente de vendas amigável e prestativo. Sua única tarefa é pegar os dados estruturados
        fornecidos e transformá-los em uma resposta única, coesa e natural para o cliente.
        
        Considere os seguintes pontos ao formular a resposta:
        - Se houver itens de pedido, confirme-os de forma clara.
        - Se houver promoções, apresente-as de forma convidativa, usando a 'descricao_para_ia'.
        - Se houver sugestões de upsell/cross-sell, integre-as de forma natural.
        - Mantenha um tom de voz consistente com a personalidade da loja.
        - Evite repetições e seja conciso.
        - Sempre termine com uma pergunta que guie o cliente para o próximo passo.
        """,
        response_model=FinalResponseData, # A IA retornará este schema
        structured_outputs=True,
        memory=memory,
        enable_user_memories=True,
        enable_session_summaries=True,
    )
