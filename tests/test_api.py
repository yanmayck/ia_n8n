import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from core import schemas
from crud import personality_crud
from sqlalchemy.orm import Session


# Testes para a API de Tenants
@pytest.mark.asyncio
@patch("services.data_sync_service.load_data_to_vector_db", new_callable=AsyncMock)
async def test_create_tenant_api(
    mock_load_data_to_vector_db, client: httpx.AsyncClient, db_session: Session
):
    print("Executando test_create_tenant_api...")
    # Criar uma personalidade primeiro
    personality_data = schemas.PersonalityCreate(
        name="api_test_personality", prompt="API test prompt"
    )
    created_personality = personality_crud.create_personality(
        db_session, personality_data
    )

    # Obter token de autenticação
    login_data = {"password": os.getenv("ADMIN_PASSWORD")}
    response = await client.post("/login", data=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Dados do formulário para a requisição
    form_data = {
        "tenant_id": "api_test_tenant",
        "nome_loja": "API Test Store",
        "ia_personality": created_personality.name,  # Passar o nome da personalidade
        "ai_prompt_description": "API test prompt",
        "endereco": "789 API Ave",
        "cep": "11223-344",
        "latitude": -22.906847,
        "longitude": -43.172896,
    }
    # Arquivo de texto em memória
    loja_txt_content = b"Informacoes da loja via API."
    files = {"loja_txt": ("loja.txt", loja_txt_content, "text/plain")}

    # Simula a requisição POST com autenticação
    response = await client.post(
        "/tenants/", data=form_data, files=files, headers=headers
    )

    # Verifica a resposta
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "api_test_tenant"
    assert data["nome_loja"] == "API Test Store"
    assert "id" in data
    mock_load_data_to_vector_db.assert_called_once()


@pytest.mark.asyncio
@patch("services.data_sync_service.load_data_to_vector_db", new_callable=AsyncMock)
async def test_create_duplicate_tenant_api(
    mock_load_data_to_vector_db, client: httpx.AsyncClient, db_session: Session
):
    # Obter token de autenticação
    login_data = {"password": os.getenv("ADMIN_PASSWORD")}
    response = await client.post("/login", data=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Dados do formulário para a requisição
    form_data = {
        "tenant_id": "duplicate_test_tenant",
        "nome_loja": "Duplicate Test Store",
        "ia_personality": "test_personality",
        "ai_prompt_description": "test prompt",
        "endereco": "123 Test St",
        "cep": "12345-678",
        "latitude": -23.550520,
        "longitude": -46.633308,
    }
    loja_txt_content = b"Informacoes da loja."
    files = {"loja_txt": ("loja.txt", loja_txt_content, "text/plain")}

    # Primeira requisição (deve ser bem-sucedida)
    response1 = await client.post(
        "/tenants/", data=form_data, files=files, headers=headers
    )
    assert response1.status_code == 200

    # Segunda requisição com o mesmo tenant_id (deve falhar)
    response2 = await client.post(
        "/tenants/", data=form_data, files=files, headers=headers
    )
    assert response2.status_code == 400
    assert "já está cadastrado" in response2.json()["detail"]


# Adicione mais testes para os outros endpoints da API aqui...
