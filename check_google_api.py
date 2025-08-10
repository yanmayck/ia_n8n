import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv() # Carrega as variáveis do .env.test
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

async def test_geocode_api_connectivity(address="Avenida Paulista, 1000, São Paulo"):
    if not GOOGLE_MAPS_API_KEY:
        print("Erro: GOOGLE_MAPS_API_KEY não configurada no .env.test")
        return

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}

    print(f"Tentando geocodificar '{address}' com a chave: {GOOGLE_MAPS_API_KEY[:5]}...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status() # Levanta erro para status 4xx/5xx
            data = response.json()

            if data["status"] == "OK" and data["results"]:
                location = data["results"][0]["geometry"]["location"]
                print(f"Sucesso! Endereço geocodificado para: {location}")
            else:
                print(f"Falha na geocodificação. Status: {data['status']}, Mensagem: {data.get('error_message', 'Nenhuma mensagem de erro.')}")
        except httpx.RequestError as e:
            print(f"Erro de rede ao chamar Geocoding API: {e}")
            print(f"Verifique sua conexão com a internet ou se há um firewall bloqueando a requisição.")
        except Exception as e:
            print(f"Erro inesperado: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_geocode_api_connectivity())
