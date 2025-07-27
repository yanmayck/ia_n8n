import os
import logging
import httpx
import json
import re
from agno.tools import tool
from agno.tools.sql import SQLTools # Importação corrigida
from duckduckgo_search import DDGS
from starlette.concurrency import run_in_threadpool
from typing import Optional, List
import asyncio
from agno.agent import Agent
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text

from core.database import SessionLocal, DATABASE_URL
from crud import tenant_crud
from core import models

logger = logging.getLogger(__name__)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

class TenantSafeSQLTools(SQLTools):
    def __init__(self, db_url: str, tenant_id: str):
        super().__init__(db_url=db_url)
        self.tenant_id = tenant_id
        logger.info(f"TenantSafeSQLTools inicializada para o tenant: {self.tenant_id}")

    def _add_tenant_filter(self, sql_query: str) -> str:
        # Adiciona um filtro de tenant_id a todas as consultas SELECT
        # Esta é uma medida de segurança para garantir o isolamento dos dados.
        if 'select' in sql_query.lower():
            if 'where' in sql_query.lower():
                # Adiciona a condição a uma cláusula WHERE existente
                sql_query = re.sub(r'(where\s+)', f"WHERE tenant_id = '{self.tenant_id}' AND ", sql_query, flags=re.IGNORECASE)
            else:
                # Adiciona uma nova cláusula WHERE
                sql_query = re.sub(r'(from\s+[\w\".]+)', f"\1 WHERE tenant_id = '{self.tenant_id}'", sql_query, flags=re.IGNORECASE)
        logger.info(f"Consulta SQL com filtro de tenant: {sql_query}")
        return sql_query

    def run_sql_query(self, query: str) -> str:
        safe_query = self._add_tenant_filter(query)
        return super().run_sql_query(safe_query)

@tool
def get_sql_query_tool(agent: Agent) -> List[TenantSafeSQLTools]:
    """Retorna uma lista de ferramentas SQL seguras para o tenant."""
    tenant_id = agent.session_state.get("tenant_id")
    if not tenant_id:
        raise ValueError("O tenant_id não foi encontrado no estado da sessão do agente.")
    
    return [TenantSafeSQLTools(db_url=DATABASE_URL, tenant_id=tenant_id)]

@tool
async def get_contextual_suggestions_tool(product_id: int) -> str:
    """
    Use esta ferramenta para obter sugestões de opcionais e produtos adicionais
    relevantes para um produto específico que o cliente acabou de pedir.
    Retorna uma lista de dicionários com 'nome' e 'preco' das sugestões.
    """
    db = SessionLocal()
    try:
        rules_engine = RulesEngine(db)
        suggestions = await run_in_threadpool(rules_engine.get_contextual_suggestions, product_id)
        return json.dumps(suggestions)
    except Exception as e:
        logger.error(f"Erro na ferramenta get_contextual_suggestions_tool: {e}", exc_info=True)
        return f"Erro ao buscar sugestões: {str(e)}"
    finally:
        db.close()

@tool
async def get_applicable_promotions_tool(tenant_id: str, order_state_json: str) -> str:
    """
    Use esta ferramenta para obter uma lista de promoções aplicáveis
    com base no ID do tenant e no estado atual do pedido (JSON string).
    Retorna uma lista de dicionários com detalhes das promoções.
    """
    db = SessionLocal()
    try:
        rules_engine = RulesEngine(db)
        order_state = json.loads(order_state_json) # Converte a string JSON de volta para dict
        promotions = await run_in_threadpool(rules_engine.get_applicable_promotions, tenant_id, order_state)
        return json.dumps(promotions)
    except Exception as e:
        logger.error(f"Erro na ferramenta get_applicable_promotions_tool: {e}", exc_info=True)
        return f"Erro ao buscar promoções aplicáveis: {str(e)}"
    finally:
        db.close()

@tool
async def freight_calculator(latitude_cliente: float, longitude_cliente: float, tenant_id: str) -> str:
    """
    Calcula o frete da loja até a localização do cliente.
    """
    db = SessionLocal()
    try:
        tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, tenant_id)
        if not tenant:
            return "Erro: Loja não encontrada."

        if not GOOGLE_MAPS_API_KEY:
            return "Erro: A chave da API do Google Maps não está configurada."
        if not tenant.latitude or not tenant.longitude:
            return "Erro: As coordenadas da loja não estão configuradas."

        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": f"{tenant.latitude},{tenant.longitude}",
            "destinations": f"{latitude_cliente},{longitude_cliente}",
            "key": GOOGLE_MAPS_API_KEY,
            "units": "metric"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data["status"] != "OK" or data["rows"][0]["elements"][0]["status"] != "OK":
            return f"Não foi possível calcular a distância. Motivo: {data.get('error_message', 'Erro desconhecido')}."

        distancia_metros = data["rows"][0]["elements"][0]["distance"]["value"]
        distancia_km = distancia_metros / 1000
        duracao_segundos = data["rows"][0]["elements"][0]["duration"]["value"]
        duracao_minutos = duracao_segundos / 60
        
        freight_cost = None
        if tenant.freight_config:
            try:
                config = json.loads(tenant.freight_config)
                config_type = config.get("type", "").upper()

                if config_type == "FIXED":
                    freight_cost = config.get("price")
                elif config_type == "PER_KM":
                    price_per_km = config.get("price_per_km")
                    if price_per_km is not None:
                        freight_cost = distancia_km * price_per_km
                elif config_type == "TIERED":
                    tiers = sorted(config.get("tiers", []), key=lambda x: x['up_to_km'])
                    for tier in tiers:
                        if distancia_km <= tier['up_to_km']:
                            freight_cost = tier['price']
                            break
                
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Erro ao processar freight_config para tenant {tenant_id}: {e}")
                pass

        return {
            "distance_km": distancia_km,
            "duration_minutes": duracao_minutos,
            "cost": freight_cost
        }

    except Exception as e:
        logger.error(f"Erro na ferramenta de cálculo de frete: {e}", exc_info=True)
        return "Ocorreu um erro interno ao tentar calcular o frete."
    finally:
        db.close()

@tool
def search_tool(query: str) -> str:
    """Use esta ferramenta para realizar uma pesquisa na web usando DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return str(results) if results else "Nenhum resultado encontrado."
    except Exception as e:
        logger.error(f"Erro na ferramenta de busca: {e}")
        return "Ocorreu um erro ao tentar pesquisar na web."
