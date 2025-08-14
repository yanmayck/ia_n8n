import json
import logging
import httpx
from agno.tools import tool
from agno.agent import Agent
from starlette.concurrency import run_in_threadpool

from core.vector_db import VectorDBManager
from core.schemas import BuscaDeProduto
from services.business_logic.promotion_service import PromotionService # Corrected import
from crud import tenant_crud

logger = logging.getLogger(__name__)

@tool
async def ferramenta_busca_avancada_produtos(query_data: BuscaDeProduto, tenant_id: str, agent: Agent) -> str:
    """Realiza uma busca avançada de produtos no cardápio."""
    db = agent.session_state.get("db")
    if not db:
        raise ValueError("Sessão de banco de dados não encontrada no session_state do agente.")
    vector_db_manager = VectorDBManager(db, collection_name=tenant_id)
    search_query = query_data.termos_gerais[0] if query_data.termos_gerais else ""
    if not search_query:
        return "Nenhum termo de busca principal fornecido."

    candidatos = await run_in_threadpool(vector_db_manager.search_documents, query=search_query, k=10)
    produtos_encontrados = []
    for doc in candidatos:
        produto_texto = doc["page_content"]
        excluir_produto = False
        if query_data.ingredientes_excluir:
            for ingrediente_excluir in query_data.ingredientes_excluir:
                if ingrediente_excluir.lower() in produto_texto.lower():
                    excluir_produto = True
                    break
        if not excluir_produto:
            produtos_encontrados.append(produto_texto)
    return json.dumps(produtos_encontrados)

@tool
async def get_contextual_suggestions_tool(product_id: int, agent: Agent) -> str:
    """Obtém sugestões contextuais para um produto."""
    db = agent.session_state.get("db")
    if not db:
        raise ValueError("Sessão de banco de dados não encontrada no session_state do agente.")
    rules_engine = PromotionService(db) # Use renamed class
    suggestions = await run_in_threadpool(rules_engine.get_contextual_suggestions, product_id)
    return json.dumps(suggestions)

@tool
async def get_applicable_promotions_tool(tenant_id: str, order_state_json: str, agent: Agent) -> str:
    """Obtém promoções aplicáveis ao pedido."""
    db = agent.session_state.get("db")
    if not db:
        raise ValueError("Sessão de banco de dados não encontrada no session_state do agente.")
    rules_engine = PromotionService(db) # Use renamed class
    order_state = json.loads(order_state_json)
    promotions = await run_in_threadpool(rules_engine.get_applicable_promotions, tenant_id, order_state)
    return json.dumps(promotions)

@tool
async def recommendation_tool(product_id: str, tenant_id: str, agent: Agent) -> str:
    """Obtém recomendações de produtos."""
    db = agent.session_state.get("db")
    if not db:
        raise ValueError("Sessão de banco de dados não encontrada no session_state do agente.")
    tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, tenant_id)
    if not tenant or not tenant.url:
        return json.dumps({"error": "URL da plataforma não configurada."})

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{tenant.url}/api/recommendations/{product_id}")
        response.raise_for_status()
        return json.dumps(response.json())
