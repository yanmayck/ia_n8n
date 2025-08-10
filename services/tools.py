import os
import logging
import httpx
import json
import re
from agno.tools import tool
from agno.tools.sql import SQLTools
from duckduckgo_search import DDGS
from starlette.concurrency import run_in_threadpool
from typing import Optional, List
import asyncio
from agno.agent import Agent
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text

from core.database import SessionLocal, DATABASE_URL
from crud import tenant_crud
from core import models, schemas
from core.vector_db import VectorDBManager
from core.schemas import BuscaDeProduto
from services.rules_engine import RulesEngine # <-- IMPORTAÇÃO ADICIONADA

logger = logging.getLogger(__name__)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

class TenantSafeSQLTools(SQLTools):
    def __init__(self, db_url: str, tenant_id: str):
        super().__init__(db_url=db_url)
        self.tenant_id = tenant_id
        logger.info(f"TenantSafeSQLTools inicializada para o tenant: {self.tenant_id}")

    def run_sql_query(self, query: str) -> str:
        if not query.lower().strip().startswith("select"):
            raise ValueError("Only SELECT queries are allowed for security reasons.")

        modified_query = query
        if "where" in query.lower():
            modified_query = f"{query} AND tenant_id = :tenant_id"
        else:
            modified_query = re.sub(r'(from\s+[\w".]+)', r'\1 WHERE tenant_id = :tenant_id', query, flags=re.IGNORECASE)

        params = {"tenant_id": self.tenant_id}

        logger.info(f"Executing SQL query with tenant filter: {modified_query} with params: {params}")
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(text(modified_query), params)
                rows = result.fetchall()
                if rows:
                    columns = result.keys()
                    formatted_results = [dict(zip(columns, row)) for row in rows]
                    return json.dumps(formatted_results, indent=2, default=str) # Add default=str for datetime
                return "No results found."
        except Exception as e:
            logger.error(f"Error executing SQL query: {e}", exc_info=True)
            raise ValueError(f"Error executing SQL query: {e}")

@tool
def get_sql_query_tool(agent: Agent) -> List[TenantSafeSQLTools]:
    """Retorna uma lista de ferramentas SQL seguras para o tenant."""
    tenant_id = agent.session_state.get("tenant_id")
    if not tenant_id:
        raise ValueError("O tenant_id não foi encontrado no estado da sessão do agente.")
    
    return [TenantSafeSQLTools(db_url=DATABASE_URL, tenant_id=tenant_id)]

@tool
async def ferramenta_busca_avancada_produtos(query_data: BuscaDeProduto, tenant_id: str, agent: Agent) -> str:
    """Realiza uma busca avançada de produtos no cardápio."""
    db = agent.session_state.get("db")
    if not db:
        raise ValueError("Sessão de banco de dados não encontrada no session_state do agente.")
    try:
        vector_db_manager = VectorDBManager(db, collection_name=tenant_id)
        search_query = query_data.termos_gerais[0] if query_data.termos_gerais else ""
        if not search_query:
            return "Nenhum termo de busca principal fornecido."

        candidatos = vector_db_manager.search_documents(query=search_query, k=10)
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
    finally:
        pass # db.close() removido, pois a sessão é gerenciada externamente

@tool
async def get_contextual_suggestions_tool(product_id: int, agent: Agent) -> str:
    """Obtém sugestões contextuais para um produto."""
    db = agent.session_state.get("db")
    if not db:
        raise ValueError("Sessão de banco de dados não encontrada no session_state do agente.")
    try:
        rules_engine = RulesEngine(db)
        suggestions = await run_in_threadpool(rules_engine.get_contextual_suggestions, product_id)
        return json.dumps(suggestions)
    except Exception as e:
        logger.error(f"Erro em get_contextual_suggestions_tool: {e}", exc_info=True)
        raise
    finally:
        pass # db.close() removido, pois a sessão é gerenciada externamente

@tool
async def get_applicable_promotions_tool(tenant_id: str, order_state_json: str, agent: Agent) -> str:
    """Obtém promoções aplicáveis ao pedido."""
    db = agent.session_state.get("db")
    if not db:
        raise ValueError("Sessão de banco de dados não encontrada no session_state do agente.")
    try:
        rules_engine = RulesEngine(db)
        order_state = json.loads(order_state_json)
        promotions = await run_in_threadpool(rules_engine.get_applicable_promotions, tenant_id, order_state)
        return json.dumps(promotions)
    finally:
        pass # db.close() removido, pois a sessão é gerenciada externamente

@tool
async def geocode_address(address: str) -> str:
    """Converte um endereço de texto em coordenadas de latitude e longitude usando a API do Google Geocoding."""
    if not GOOGLE_MAPS_API_KEY:
        return json.dumps({"error": "A chave da API do Google Maps não está configurada no servidor."})

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}

    logger.debug(f"Geocoding API Request: URL={url}, Params={params}") # Adicionado log
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, params=params)
            logger.debug(f"Geocoding API Response Status: {response.status_code}, Body: {response.text}") # Adicionado log
            response.raise_for_status() # Levanta erro para status 4xx/5xx
            data = response.json()

            if data["status"] == "OK" and data["results"]:
                location = data["results"][0]["geometry"]["location"]
                return json.dumps(location) # Retorna {'lat': ..., 'lng': ...}
            else:
                error_message = data.get("error_message", f"Geocoding falhou com status: {data['status']}")
                logger.error(f"Erro de Geocoding: {error_message}")
                return json.dumps({"error": error_message})
        except httpx.RequestError as e:
            logger.error(f"Erro de rede ao chamar Geocoding API: {e}", exc_info=True) # Adicionado exc_info
            return json.dumps({"error": f"Erro de rede ao contatar o serviço de mapas: {e}"})

@tool
async def freight_calculator(client_latitude: float, client_longitude: float, tenant_id: str, db: Session) -> str:
    """
    Calcula o frete da loja até a localização do cliente.
    Recebe as coordenadas do cliente, o ID da loja (tenant_id) e a sessão do banco de dados diretamente.
    """
    logger.debug(f"TOOL_TRACE: Entered freight_calculator tool function for tenant {tenant_id}.")
    
    if not GOOGLE_MAPS_API_KEY:
        return json.dumps({"error": "A chave da API do Google Maps não está configurada no servidor."})

    try:
        tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, tenant_id)
        if not tenant or not tenant.latitude or not tenant.longitude:
            return json.dumps({"error": "Configuração de frete da loja (coordenadas) insuficiente para o cálculo."})

        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": f"{tenant.latitude},{tenant.longitude}",
            "destinations": f"{client_latitude},{client_longitude}",
            "key": GOOGLE_MAPS_API_KEY,
            "units": "metric"
        }
        logger.debug(f"Distance Matrix API Request: URL={url}, Params={params}")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            logger.debug(f"Distance Matrix API Response Status: {response.status_code}, Body: {response.text}")
            response.raise_for_status()
            data = response.json()

        if data["status"] != "OK" or data["rows"][0]["elements"][0]["status"] != "OK":
            error_msg = data.get('error_message', 'Erro desconhecido na API de mapas.')
            logger.error(f"Erro da API do Google Maps: {error_msg}", exc_info=True)
            return json.dumps({"error": error_msg})

        distancia_km = data["rows"][0]["elements"][0]["distance"]["value"] / 1000
        duracao_minutos = data["rows"][0]["elements"][0]["duration"]["value"] / 60
        
        freight_cost = None
        if tenant.freight_config:
            try:
                config = json.loads(tenant.freight_config)
                if config.get("type", "").upper() == "FIXED":
                    freight_cost = config.get("price")
                elif config.get("type", "").upper() == "PER_KM":
                    freight_cost = distancia_km * config.get("price_per_km", 0)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Erro ao processar a configuração de frete (freight_config) do tenant {tenant_id}: {e}", exc_info=True)

        return json.dumps({
            "distance_km": distancia_km,
            "duration_minutes": duracao_minutos,
            "cost": freight_cost,
            "origin_address": tenant.endereco,
            "destination_latitude": client_latitude,
            "destination_longitude": client_longitude
        })
    except httpx.RequestError as e:
        logger.error(f"Erro de rede ao chamar Distance Matrix API: {e}", exc_info=True)
        return json.dumps({"error": f"Erro de rede ao contatar o serviço de mapas: {e}"})
    except Exception as e:
        logger.error(f"Erro na calculadora de frete: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

@tool
def search_tool(query: str) -> str:
    """Realiza uma pesquisa na web."""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return str(results) if results else "Nenhum resultado encontrado."
    except Exception as e:
        logger.error(f"Erro na ferramenta de busca: {e}")
        return "Ocorreu um erro ao pesquisar."

@tool
async def recommendation_tool(product_id: str, tenant_id: str, agent: Agent) -> str:
    """Obtém recomendações de produtos."""
    db = agent.session_state.get("db")
    if not db:
        raise ValueError("Sessão de banco de dados não encontrada no session_state do agente.")
    try:
        tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, tenant_id)
        if not tenant or not tenant.url:
            return json.dumps({"error": "URL da plataforma não configurada."})

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{tenant.url}/api/recommendations/{product_id}")
            response.raise_for_status()
            return json.dumps(response.json())
    finally:
        pass # db.close() removido, pois a sessão é gerenciada externamente
