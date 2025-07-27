from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import pytest
from unittest.mock import patch, MagicMock

# Este fixture 'client' e 'db_session' virão do conftest.py
# Não precisamos defini-los aqui, apenas usá-los.

@patch('services.chat_service.handle_message')
def test_ai_endpoint_success(mock_handle_message, client: TestClient, db_session: Session, test_tenant):
    # Mock da resposta do serviço de chat
    mock_handle_message.return_value = {
        "response_text": "Olá! Como posso ajudar?",
        "human_handoff": False,
        "send_menu": False,
        "freight_details": None,
        "file_summary": None
    }

    # Dados de requisição válidos
    request_data = {
        "message_user": "Oi, tudo bem?",
        "tenant_id": test_tenant.tenant_id,
        "user_phone": "5511999999999",
        "whatsapp_message_id": "whatsapp_123"
    }

    response = client.post("/ai", json=request_data)

    assert response.status_code == 200
    # A API retorna uma lista de partes, então verificamos se a parte de texto está correta
    response_json = response.json()
    assert isinstance(response_json, list)
    assert len(response_json) > 0
    text_part = next((part for part in response_json if part['type'] == 'text'), None)
    assert text_part is not None
    assert text_part['text_content'] == "Olá! Como posso ajudar?"
    mock_handle_message.assert_called_once()

@patch('services.chat_service.handle_message')
def test_ai_endpoint_empty_message(mock_handle_message, client: TestClient, db_session: Session, test_tenant):
    # Mock da resposta do serviço de chat
    mock_handle_message.return_value = {
        "response_text": "Por favor, diga algo.",
        "human_handoff": False,
        "send_menu": False,
        "freight_details": None,
        "file_summary": None
    }

    request_data = {
        "message_user": "", # Mensagem vazia
        "tenant_id": test_tenant.tenant_id,
        "user_phone": "5511999999999",
        "whatsapp_message_id": "whatsapp_124"
    }

    response = client.post("/ai", json=request_data)

    assert response.status_code == 200
    # A API retorna uma lista de partes
    response_json = response.json()
    assert isinstance(response_json, list)
    assert len(response_json) > 0
    text_part = next((part for part in response_json if part['type'] == 'text'), None)
    assert text_part is not None
    assert text_part['text_content'] == "Por favor, diga algo."
    mock_handle_message.assert_called_once()

def test_ai_endpoint_missing_required_fields(client: TestClient, db_session: Session):
    # Teste com campos obrigatórios faltando (ex: tenant_id)
    request_data = {
        "message_user": "Teste",
        "user_phone": "5511999999999",
        "whatsapp_message_id": "whatsapp_125"
    }

    response = client.post("/ai", json=request_data)

    assert response.status_code == 422 # Unprocessable Entity (erro de validação Pydantic)
    assert "detail" in response.json()
        # A validação do Pydantic deve reclamar do campo 'tenant_id'
    assert "tenant_id" in response.text


def test_ai_endpoint_invalid_tenant_id(client: TestClient, db_session: Session):
    # Não precisamos mockar nada aqui, pois a exceção será levantada antes.
    request_data = {
        "message_user": "Qual o menu?",
        "tenant_id": "non_existent_tenant", # Tenant ID que não existe
        "user_phone": "5511999999999",
        "whatsapp_message_id": "whatsapp_126"
    }

    response = client.post("/ai", json=request_data)

    assert response.status_code == 404 # Esperamos 404 Not Found
    assert response.json()["detail"] == "Cliente com o ID 'non_existent_tenant' não foi encontrado ou está inativo."