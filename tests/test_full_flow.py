import pytest
import os
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from core.models import Tenant
from crud import product_crud
from core.schemas import ProductCreate
import logging
import uuid

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
integration_test_reason = "GEMINI_API_KEY não está configurada no ambiente de teste"

def ask_ai_endpoint(client: TestClient, message: str, tenant_id: str, session_id: str, user_id: str):
    """Helper para fazer chamadas à rota /ai e retornar o corpo da resposta."""
    unique_message_id = f"whatsapp_{uuid.uuid4()}"
    request_data = {
        "message_user": message,
        "tenant_id": tenant_id,
        "user_phone": user_id,
        "whatsapp_message_id": unique_message_id
    }
    response = client.post("/ai", json=request_data)
    assert response.status_code == 200, f"A API retornou um erro: {response.text}"
    return response.json()

@pytest.mark.integration
@pytest.mark.skipif(not GEMINI_API_KEY, reason=integration_test_reason)
@pytest.mark.asyncio
async def test_complete_order_flow(client: TestClient, db_session: Session, test_tenant: Tenant):
    """
    Testa um fluxo de conversação completo através da rota /ai, 
    simulando um usuário real e validando as respostas da IA.
    """
    session_id = f"test_full_flow_e2e_session_{uuid.uuid4()}"
    user_id = "user_full_flow_e2e"

    # --- PASSO 1: Adicionar produtos ao cardápio do tenant ---
    logger.info(f"[{session_id}] - PASSO 1: Configurando produtos no banco de dados.")
    product1 = ProductCreate(nome_produto="Pizza de Calabresa", preco_base=45.50, descricao_produto="Molho de tomate, queijo, calabresa e cebola.", categoria_produto="Pizzas Salgadas")
    product2 = ProductCreate(nome_produto="Pizza de Quatro Queijos", preco_base=50.00, descricao_produto="Molho de tomate, mussarela, provolone, parmesão e gorgonzola.", categoria_produto="Pizzas Salgadas")
    product_crud.create_product(db_session, product1, tenant_id=test_tenant.tenant_id)
    product_crud.create_product(db_session, product2, tenant_id=test_tenant.tenant_id)
    
    # Garante que a sessão do DB seja atualizada com os novos produtos
    db_session.commit()

    # --- PASSO 2: Pedir o cardápio ---
    logger.info(f"[{session_id}] - PASSO 2: Pedindo o cardápio via rota /ai.")
    response_parts = ask_ai_endpoint(client, "Qual o cardápio de vocês?", test_tenant.tenant_id, session_id, user_id)
    
    # A resposta deve ser uma lista de partes, pegamos o conteúdo de texto
    text_content = "".join([part.get("text_content", "") for part in response_parts if part.get("type") == "text"])
    logger.info(f"[{session_id}] - Resposta da IA (Cardápio): {text_content}")

    # Validações: A IA deve listar os produtos que estão no banco de dados.
    # Não deve inventar itens ou pedir o endereço.
    assert "calabresa" in text_content.lower()
    assert "quatro queijos" in text_content.lower()
    assert "r$ 45,50" in text_content.replace(".", ",")
    assert "r$ 50,00" in text_content.replace(".", ",")
    assert "endereço" not in text_content.lower() # Garante que a IA não pulou para o passo de frete

    # --- PASSO 3: Fazer uma pergunta geral sobre o horário ---
    logger.info(f"[{session_id}] - PASSO 3: Perguntando o horário de funcionamento.")
    response_parts = ask_ai_endpoint(client, "qual o horário de funcionamento?", test_tenant.tenant_id, session_id, user_id)
    text_content = "".join([part.get("text_content", "") for part in response_parts if part.get("type") == "text"])
    logger.info(f"[{session_id}] - Resposta da IA (Horário): {text_content}")

    # Validação: A IA deve usar a informação do `config_ai` do `test_tenant`
    assert "11h" in text_content.lower()
    assert "23h" in text_content.lower()

    logger.info(f"[{session_id}] - Fluxo de teste de ponta a ponta concluído com sucesso!")