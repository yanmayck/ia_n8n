import logging
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from core.models import Tenant
from core.schemas import ProductCreate
from crud import product_crud
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
integration_test_reason = "GEMINI_API_KEY não está configurada no ambiente de teste"


async def ask_ai_endpoint(
    client: httpx.AsyncClient,
    message: str,
    tenant_id: str,
    user_id: str,
    latitude: float = None,
    longitude: float = None,
):
    """Helper para fazer chamadas à rota /ai e retornar o corpo da resposta."""
    # Gera um ID de mensagem único para cada chamada, como o WhatsApp faria
    unique_message_id = f"whatsapp_{uuid.uuid4()}"
    request_data = {
        "message_user": message,
        "tenant_id": tenant_id,
        "user_phone": user_id,  # O user_id consistente é o telefone do usuário
        "whatsapp_message_id": unique_message_id,  # O ID único da mensagem
        "latitude": latitude,
        "longitude": longitude,
    }
    response = await client.post("/ai", json=request_data)
    assert response.status_code == 200, f"A API retornou um erro: {response.text}"
    return response.json()


def get_text_from_response(response_parts: list) -> str:
    """Extrai e concatena todo o conteúdo de texto da resposta da API."""
    return "".join(
        [
            part.get("text_content", "")
            for part in response_parts
            if part.get("type") == "text"
        ]
    ).lower()


@pytest.mark.integration
@pytest.mark.skipif(not GEMINI_API_KEY, reason=integration_test_reason)
@pytest.mark.asyncio
@patch("services.main_orchestrator.save_order_to_platform", new_callable=AsyncMock)
async def test_complete_order_flow(
    mock_save_order: MagicMock,
    client: httpx.AsyncClient,
    db_session: Session,
    test_tenant: Tenant,
):
    """
    Testa o fluxo de conversação de pedido completo, seguindo a nova lógica do MVP.
    """
    user_id = "user_full_flow_e2e"
    conversation_log = []

    async def log_and_ask(message, lat=None, lon=None):
        """Função auxiliar para registrar a conversa e chamar a API."""
        logger.info(f"--> USUÁRIO: {message}")
        response_json = await ask_ai_endpoint(
            client, message, test_tenant.tenant_id, user_id, lat, lon
        )
        text_response = get_text_from_response(response_json)
        logger.info(f"<-- IA: {text_response}")
        conversation_log.append({"user": message, "ai": text_response})
        return response_json, text_response

    # --- PASSO 1: Configuração do Ambiente ---
    product1 = ProductCreate(
        nome_produto="Pizza de Calabresa",
        preco_base=45.50,
        descricao_produto="Molho de tomate, queijo, calabresa e cebola.",
    )
    product2 = ProductCreate(
        nome_produto="Refrigerante 2L",
        preco_base=10.00,
        descricao_produto="Coca-cola, Guaraná ou Fanta",
    )
    product_crud.create_product(db_session, product1, tenant_id=test_tenant.tenant_id)
    product_crud.create_product(db_session, product2, tenant_id=test_tenant.tenant_id)
    db_session.commit()

    # --- PASSO 2: Execução da Conversa (Novo Fluxo) ---
    await log_and_ask("Boa noite")
    await log_and_ask("gostaria de uma pizza de calabresa e um refrigerante 2l")
    await log_and_ask("só isso, pode fechar a conta")
    await log_and_ask(
        "Pode ser no pix. Meu endereço é Avenida Paulista, 1000, São Paulo"
    )
    await log_and_ask("sim, confirmo")

    # --- PASSO 3: Validação Final ---
    mock_save_order.assert_called_once()

    # Verifica os dados que foram enviados para a plataforma
    sent_order_data = mock_save_order.call_args.kwargs
    logger.info(f"DADOS ENVIADOS PARA A PLATAFORMA: {sent_order_data}")

    assert sent_order_data["user_id"] == user_id
    assert sent_order_data["tenant_id"] == test_tenant.tenant_id
    assert sent_order_data["payment_method"] == "pix"
    assert "Avenida Paulista, 1000" in sent_order_data["address"]

    # Verifica os itens do pedido
    sent_items = sent_order_data["items"]
    assert len(sent_items) == 2
    assert any(item["product_name"] == "Pizza de Calabresa" for item in sent_items)
    assert any(item["product_name"] == "Refrigerante 2L" for item in sent_items)

    # --- PASSO 4: Log da Conversa para Análise ---
    logger.info("--- LOG COMPLETO DA CONVERSA PARA ANÁLISE ---")
    for entry in conversation_log:
        logger.info(f"USER: {entry['user']}\nAI: {entry['ai']}\n")
    logger.info("---------------------------------------------")
