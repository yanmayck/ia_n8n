import logging
import os
from unittest.mock import patch

import pytest

from core.models import Tenant
from core.schemas import OrderState

from services.main_orchestrator import OrchestratorAgent
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "fake_api_key_for_testing")
integration_test_reason = "GEMINI_API_KEY ou GOOGLE_MAPS_API_KEY não configurada no ambiente"


# --- Testes de Integração (Chamadas Reais) ---


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") or not os.getenv("GOOGLE_MAPS_API_KEY"),
    reason=integration_test_reason,
)
@pytest.mark.asyncio
async def test_freight_calculation_with_text_address(db_session: Session, test_tenant: Tenant):
    """Testa se o orquestrador consegue lidar com um endereço em texto, usando a API real."""
    orchestrator = OrchestratorAgent(
        db=db_session,
        session_id="test_text_address_real_api",
        tenant_id=test_tenant.tenant_id,
        user_id="user_text_address_real_api",
        api_key=GEMINI_API_KEY,
    )

    # Simula o estado do pedido, que é recuperado no início do process_message
    with patch(
        "services.state_manager.state_manager.get_order_state",
        return_value=OrderState(),
    ):
        result = await orchestrator.process_message(
            message="qual o frete para Avenida Paulista, 1578, São Paulo?",
            personality_prompt="Você é um assistente de delivery.",
        )

    # A verificação agora é sobre o resultado final
    assert result.freight_details is not None
    assert result.freight_details.cost > 0
    # A resposta final da IA deve conter o valor do frete formatado
    assert "R$ 12,50" in result.response_text.replace(".", ",")


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason=integration_test_reason)
@pytest.mark.asyncio
async def test_general_question_makes_real_api_call(db_session: Session, test_tenant: Tenant):
    """Testa se o RAG busca informações da loja corretamente."""
    orchestrator = OrchestratorAgent(
        db=db_session,
        session_id="test_real_api_general",
        tenant_id=test_tenant.tenant_id,
        user_id="user_real_api_general",
        api_key=GEMINI_API_KEY,
    )

    result = await orchestrator.process_message(
        message="qual o horário de funcionamento de vocês?",
        personality_prompt="Você é um assistente de pizzaria.",
    )

    response_lower = result.response_text.lower()
    assert "11h" in response_lower and "23h" in response_lower
