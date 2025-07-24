import logging
import httpx

logger = logging.getLogger(__name__)

async def calcular_frete_google_maps_async(
    origem_lat: float,
    origem_lng: float,
    destino_lat: float,
    destino_lng: float,
    api_key: str
) -> float:
    """Calcula a distância em km entre dois pontos usando a Google Maps Distance Matrix API."""
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origem_lat},{origem_lng}",
        "destinations": f"{destino_lat},{destino_lng}",
        "key": api_key,
        "units": "metric"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()  # Levanta uma exceção para status de erro HTTP
        data = response.json()

    if data["status"] == "OK" and data["rows"][0]["elements"][0]["status"] == "OK":
        distancia_metros = data["rows"][0]["elements"][0]["distance"]["value"]
        distancia_km = distancia_metros / 1000
        return distancia_km
    else:
        error_message = data.get("error_message", "Erro desconhecido na API do Google Maps")
        logger.error(f"Erro ao calcular frete pela API do Google Maps: {error_message}")
        raise Exception(f"Erro ao calcular frete: {error_message}")
