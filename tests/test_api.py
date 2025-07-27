import os
import os
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import pytest
from core import schemas
from crud import personality_crud

from unittest.mock import patch

# Testes para a API de Tenants
@patch('services.agent_manager.load_data_to_vector_db')
def test_create_tenant_api(mock_load_data_to_vector_db, client: TestClient, db_session: Session):
    print("Executando test_create_tenant_api...")
    # Criar uma personalidade primeiro
    personality_data = schemas.PersonalityCreate(name="api_test_personality", prompt="API test prompt")
    created_personality = personality_crud.create_personality(db_session, personality_data)

    # Obter token de autenticação
    login_data = {"password": os.getenv("ADMIN_PASSWORD")}
    response = client.post("/login", data=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Dados do formulário para a requisição
    form_data = {
        'tenant_id': 'api_test_tenant',
        'nome_loja': 'API Test Store',
        'ia_personality': created_personality.id,
        'ai_prompt_description': 'API test prompt',
        'endereco': '789 API Ave',
        'cep': '11223-344',
        'latitude': -22.906847,
        'longitude': -43.172896
    }
    # Arquivo de texto em memória
    loja_txt_content = b"Informacoes da loja via API."
    files = {'loja_txt': ('loja.txt', loja_txt_content, 'text/plain')}

    # Simula a requisição POST com autenticação
    response = client.post("/tenants/", data=form_data, files=files, headers=headers)

    # Verifica a resposta
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "api_test_tenant"
    assert data["nome_loja"] == "API Test Store"
    assert "id" in data

# Adicione mais testes para os outros endpoints da API aqui...
