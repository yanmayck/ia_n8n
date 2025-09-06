import logging
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from core.models import Tenant
from core.schemas import MenuImageCreate, ProductCreate, PromocaoCreate
from crud import menu_image_crud, product_crud, promocao_crud
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
    mock_send_order: MagicMock,
    client: httpx.AsyncClient,
    db_session: Session,
    test_tenant: Tenant,
):
    """
    Testa um fluxo de conversação de pedido completo, focando no resultado final (dados enviados)
    em vez de validar cada resposta intermediária da IA.
    """
    session_id = f"test_full_flow_e2e_session_{uuid.uuid4()}"
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

    # --- PASSO 1: Configuração do Ambiente (Produtos, Promoções e Imagem de Cardápio) ---
    logger.info(
        f"[{user_id}] - PASSO 1: Configurando produtos, promoções e imagem de cardápio no DB."
    )
    product1 = ProductCreate(
        nome_produto="Pizza de Calabresa",
        preco_base=45.50,
        descricao_produto="Molho de tomate, queijo, calabresa e cebola.",
        categoria_produto="Pizzas Salgadas",
    )
    product2 = ProductCreate(
        nome_produto="Pizza de Quatro Queijos",
        preco_base=50.00,
        descricao_produto="Molho de tomate, mussarela, provolone, parmesão e gorgonzola.",
        categoria_produto="Pizzas Salgadas",
    )
    product3 = ProductCreate(
        nome_produto="Refrigerante 2L",
        preco_base=10.00,
        descricao_produto="Coca-cola, Guaraná ou Fanta",
        categoria_produto="Bebidas",
    )
    promo = PromocaoCreate(
        nome_promocao="Borda Recheada Grátis",
        descricao_para_ia="Na compra de qualquer pizza grande, a borda recheada com catupiry é por nossa conta!",
        acao_json={"tipo_desconto": "brinde", "valor_desconto": 0.0},
        is_ativa=True,
    )
    menu_image = MenuImageCreate(
        image_url="http://example.com/menu.jpg", description="Cardapio Principal"
    )

    product_crud.create_product(db_session, product1, tenant_id=test_tenant.tenant_id)
    product_crud.create_product(db_session, product2, tenant_id=test_tenant.tenant_id)
    product_crud.create_product(db_session, product3, tenant_id=test_tenant.tenant_id)
    promocao_crud.create_promocao(db_session, promo, tenant_id=test_tenant.tenant_id)
    menu_image_crud.create_menu_image(
        db_session, menu_image, tenant_id=test_tenant.tenant_id
    )
    db_session.commit()

    # --- PASSO 2: Execução da Conversa ---
    logger.info(f"[{session_id}] - PASSO 2: Executando a conversa completa.")
    await log_and_ask("Boa noite")
    response, _ = await log_and_ask("qual o cardapio?")
    assert any(part.get("send_menu") for part in response), (
        "A flag 'send_menu' não foi ativada no passo de pedir o cardápio."
    )

    await log_and_ask("eu gostaria de uma pizza de calabresa e um refrigerante 2l")
    await log_and_ask("ah, pode tirar o refrigerante por favor")
    await log_and_ask(
        "pode fechar a conta. meu endereço é Avenida Paulista, 1000, São Paulo"
    )
    await log_and_ask("isso, pode confirmar")

    # --- PASSO 3: Validação Final (O que realmente importa) ---
    logger.info(
        f"[{session_id}] - PASSO 3: Verificando se o pedido foi enviado corretamente para a plataforma."
    )

    mock_send_order.assert_called_once()

    sent_order_data = mock_send_order.call_args.kwargs
    logger.info(f"DADOS ENVIADOS PARA A PLATAFORMA: {sent_order_data}")

    assert sent_order_data["user_id"] == user_id
    assert len(sent_order_data["items"]) == 1
    assert sent_order_data["items"][0]["product_name"] == "Pizza de Calabresa"
    assert sent_order_data["address"] is not None
    assert "avenida paulista, 1000" in sent_order_data["address"].lower()

    # --- PASSO 4: Log da Conversa para Validação Manual ---
    logger.info(
        f"[{session_id}] - Fluxo de teste de ponta a ponta concluído com sucesso!"
    )
    logger.info("--- LOG COMPLETO DA CONVERSA PARA ANÁLISE ---")
    for entry in conversation_log:
        logger.info(f"USER: {entry['user']}\nAI: {entry['ai']}\n")
    logger.info("---------------------------------------------")