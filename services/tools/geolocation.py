import os
import logging
import httpx
import json
from agno.tools import tool
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from crud import tenant_crud

logger = logging.getLogger(__name__)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

@tool
async def geocode_address(address: str) -> str:
    """Converte um endereço de texto em coordenadas de latitude e longitude usando a API do Google Geocoding."""
    if not GOOGLE_MAPS_API_KEY:
        return json.dumps({"error": "A chave da API do Google Maps não está configurada no servidor."})

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}

    logger.debug(f"Geocoding API Request: URL={url}, Params={params}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, params=params)
            logger.debug(f"Geocoding API Response Status: {response.status_code}, Body: {response.text}")
            response.raise_for_status()
            data = response.json()

            if data["status"] == "OK" and data["results"]:
                location = data["results"][0]["geometry"]["location"]
                return json.dumps(location)
            else:
                error_message = data.get("error_message", f"Geocoding falhou com status: {data['status']}")
                logger.error(f"Erro de Geocoding: {error_message}")
                return json.dumps({"error": error_message})
        except httpx.RequestError as e:
            logger.error(f"Erro de rede ao chamar Geocoding API: {e}", exc_info=True)
            return json.dumps({"error": f"Erro de rede ao contatar o serviço de mapas: {e}"})

@tool
async def freight_calculator(client_latitude: float, client_longitude: float, tenant_id: str, db: Session) -> str:
    """
    Calcula o frete da loja até a localização do cliente.
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
