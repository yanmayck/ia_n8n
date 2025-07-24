import os
import logging
import httpx
import json
from agno.tools import tool
from duckduckgo_search import DDGS
from starlette.concurrency import run_in_threadpool
from typing import Optional

from core.database import SessionLocal
from crud import tenant_crud, product_crud # Importar product_crud
from core import models # Importar models para acessar o modelo Product

logger = logging.getLogger(__name__)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

@tool
async def freight_calculator(latitude_cliente: float, longitude_cliente: float, tenant_id: str) -> str:
    """
    Calcula o frete da loja até a localização do cliente.
    Primeiro, obtém a distância via Google Maps.
    Depois, calcula o custo com base na configuração de frete do tenant (JSON).
    Formatos de JSON suportados:
    - Fixo: {"type": "FIXED", "price": 10.00}
    - Por KM: {"type": "PER_KM", "price_per_km": 2.50}
    - Por Faixa: {"type": "TIERED", "tiers": [{"up_to_km": 3, "price": 5.00}, {"up_to_km": 999, "price": 10.00}]}
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

        # 1. Obter distância da Google Maps API
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
        
        # 2. Calcular custo com base na configuração de frete (freight_config)
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
                # Se a configuração for inválida, não calcula o custo, mas ainda retorna a distância.
                pass

        # 3. Construir a resposta final
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
async def product_query_tool(tenant_id: str, query_type: str, product_name: Optional[str] = None) -> str:
    """
    Consulta informações sobre produtos para um tenant específico.
    query_type: 'mais_caro', 'mais_barato', 'buscar_por_nome', 'listar_todos'.
    product_name (opcional): O nome do produto para buscar_por_nome.
    """
    db = SessionLocal()
    try:
        products = await run_in_threadpool(product_crud.get_products_by_tenant_id, db, tenant_id=tenant_id)
        if not products:
            return "Nenhum produto encontrado para esta loja."

        if query_type == "mais_caro":
            # Filtrar produtos que têm preço válido e convertê-lo para float
            valid_products = []
            for p in products:
                try:
                    p_price = float(p.price)
                    valid_products.append((p, p_price))
                except ValueError:
                    logger.warning(f"Produto {p.name} com preço inválido: {p.price}")
                    continue
            
            if not valid_products:
                return "Não foi possível determinar o produto mais caro devido a preços inválidos."

            most_expensive = max(valid_products, key=lambda item: item[1])[0]
            return f"O produto mais caro é '{most_expensive.name}' por R$ {float(most_expensive.price):.2f}."

        elif query_type == "mais_barato":
            valid_products = []
            for p in products:
                try:
                    p_price = float(p.price)
                    valid_products.append((p, p_price))
                except ValueError:
                    logger.warning(f"Produto {p.name} com preço inválido: {p.price}")
                    continue
            
            if not valid_products:
                return "Não foi possível determinar o produto mais barato devido a preços inválidos."

            most_cheapest = min(valid_products, key=lambda item: item[1])[0]
            return f"O produto mais barato é '{most_cheapest.name}' por R$ {float(most_cheapest.price):.2f}."

        elif query_type == "buscar_por_nome":
            if not product_name:
                return "Por favor, forneça o nome do produto para buscar."
            found_product = next((p for p in products if p.name.lower() == product_name.lower()), None)
            if found_product:
                return f"Detalhes do produto '{found_product.name}': Preço R$ {float(found_product.price):.2f}. Descrição: {found_product.principais_funcionalidades or 'N/A'}. Público-alvo: {found_product.publico_alvo or 'N/A'}."
            return f"Produto '{product_name}' não encontrado."

        elif query_type == "listar_todos":
            if not products:
                return "Nenhum produto cadastrado."
            product_list = [f"{p.name} (R$ {float(p.price):.2f})" for p in products]
            return "Nossos produtos são: " + ", ".join(product_list) + "."

        return "Tipo de consulta de produto não reconhecido."

    except Exception as e:
        logger.error(f"Erro na ferramenta de consulta de produtos: {e}", exc_info=True)
        return "Ocorreu um erro interno ao consultar os produtos."
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
