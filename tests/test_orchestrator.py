import pytest
import os
import base64
import json
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session

from services.main_orchestrator import OrchestratorAgent
from core.schemas import AnaliseDeIntencao, TarefaIdentificada, AIResponse, FinalResponseData, BuscaDeProduto, ModificacaoItem, OrderTakingOutput, OrderItem, FreightDetails, OrderState
from core import models, schemas
from crud import tenant_crud
from agno.workflow.v2.types import StepInput, StepOutput, StepMetrics
from agno.agent import RunResponse
from agno.workflow.v2.workflow import WorkflowRunResponse
from core.models import Tenant
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "fake_api_key_for_testing")
integration_test_reason = "GEMINI_API_KEY não configurada no ambiente"

@pytest.mark.asyncio
async def test_orchestrator_routes_to_general_question_mocked(db_session: Session, test_tenant: Tenant):
    orchestrator = OrchestratorAgent(db=db_session, session_id="test_session_general_mocked", tenant_id=test_tenant.tenant_id, user_id="user_general_mocked_test", api_key=GEMINI_API_KEY)
    
    receptionist_response = RunResponse(
        content=AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa="fazer_pergunta_geral")])
    )
    formulation_response = RunResponse(
        content=FinalResponseData(text_response="Nós fechamos às 23h.")
    )
    final_workflow_response = WorkflowRunResponse(content=formulation_response.content)

    with patch.object(orchestrator.workflow, 'arun', new_callable=AsyncMock, return_value=final_workflow_response) as mock_workflow_run:
        result = await orchestrator.process_message(message="que horas voces fecham?", personality_prompt="test")

        mock_workflow_run.assert_called_once()
        assert "Nós fechamos às 23h." in result.response_text

@pytest.mark.asyncio
async def test_order_taking_avoids_real_api_call(db_session: Session, test_tenant: Tenant):
    orchestrator = OrchestratorAgent(db=db_session, session_id="test_mock_api_order", tenant_id=test_tenant.tenant_id, user_id="user_mock_api_order", api_key=GEMINI_API_KEY)
    
    receptionist_response = RunResponse(
        content=AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa="adicionar_item")])
    )
    formulation_response = RunResponse(content=FinalResponseData(text_response="Pedido anotado com sucesso."))
    final_workflow_response = WorkflowRunResponse(content=formulation_response.content)

    with patch.object(orchestrator.workflow, 'arun', new_callable=AsyncMock, return_value=final_workflow_response) as mock_workflow_run:
        result = await orchestrator.process_message(message="Eu quero duas pizzas.", personality_prompt="test")
        
        mock_workflow_run.assert_called_once()
        assert "Pedido anotado com sucesso" in result.response_text

@pytest.mark.asyncio
async def test_freight_calculation_avoids_real_api_call(db_session: Session, test_tenant: Tenant):
    orchestrator = OrchestratorAgent(db=db_session, session_id="test_mock_api_freight", tenant_id=test_tenant.tenant_id, user_id="user_mock_api_freight", api_key=GEMINI_API_KEY)
    
    freight_details = FreightDetails(distance_km=5.5, cost=10.0, destination_latitude=-23.561, destination_longitude=-46.656, origin_latitude=0.0, origin_longitude=0.0)
    formulation_response = RunResponse(content=FinalResponseData(text_response="O frete é R$ 10.00", freight_details=freight_details))
    
    final_workflow_response = WorkflowRunResponse(content=formulation_response.content)
    final_workflow_response.additional_data = {"freight_details": freight_details}

    with patch.object(orchestrator.workflow, 'arun', new_callable=AsyncMock, return_value=final_workflow_response) as mock_workflow_run:
        result = await orchestrator.process_message(message="frete?", personality_prompt="test", client_latitude=-23.561, client_longitude=-46.656)

        mock_workflow_run.assert_called_once()
        assert "R$ 10.00" in result.response_text
        assert result.freight_details is not None
        assert result.freight_details.cost == 10.0

# --- Testes de Integração ---

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY") or not os.getenv("GOOGLE_MAPS_API_KEY"), reason=f"{integration_test_reason} or GOOGLE_MAPS_API_KEY not set")
@pytest.mark.asyncio
async def test_freight_calculation_makes_real_api_call(db_session: Session, test_tenant: Tenant):
    session_id = "test_real_api_freight"
    logger.info(f"[{session_id}] - INICIO test_freight_calculation_makes_real_api_call")
    orchestrator = OrchestratorAgent(db=db_session, session_id=session_id, tenant_id=test_tenant.tenant_id, user_id="user_real_api_freight", api_key=GEMINI_API_KEY)
    
    with patch('services.state_manager.state_manager.get_order_state', return_value=OrderState()):
        result = await orchestrator.process_message(
            message="quanto custa a entrega para este local?",
            personality_prompt="Você é um assistente de delivery.",
            client_latitude=-23.561, 
            client_longitude=-46.656  
        )

    print(f"Resposta real da IA (Frete): {result.response_text}")
    assert result.response_text and len(result.response_text) > 0
    assert result.freight_details is not None

    assert result.freight_details.cost > 0
    logger.info(f"[{session_id}] - FIM test_freight_calculation_makes_real_api_call")


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason=integration_test_reason)
@pytest.mark.asyncio
async def test_general_question_makes_real_api_call(db_session: Session, test_tenant: Tenant):
    session_id = "test_real_api_general"
    logger.info(f"[{session_id}] - INICIO test_general_question_makes_real_api_call")
    orchestrator = OrchestratorAgent(db=db_session, session_id=session_id, tenant_id=test_tenant.tenant_id, user_id="user_real_api_general", api_key=GEMINI_API_KEY)
    
    result = await orchestrator.process_message(
        message="qual o horário de funcionamento de vocês?",
        personality_prompt="Você é um assistente de pizzaria."
    )

    print(f"Resposta real da IA (Pergunta Geral): {result.response_text}")
    assert result.response_text and len(result.response_text) > 0
    response_lower = result.response_text.lower()
    assert "11" in response_lower and "23" in response_lower
    logger.info(f"[{session_id}] - FIM test_general_question_makes_real_api_call")

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY") or not os.getenv("GOOGLE_MAPS_API_KEY"), reason=f"{integration_test_reason} or GOOGLE_MAPS_API_KEY not set")
@pytest.mark.asyncio
async def test_freight_calculation_with_text_address(db_session: Session, test_tenant: Tenant):
    """Testa se o orquestrador consegue lidar com um endereço em texto, usando a API real."""
    orchestrator = OrchestratorAgent(
        db=db_session,
        session_id="test_text_address_real_api",
        tenant_id=test_tenant.tenant_id,
        user_id="user_text_address_real_api",
        api_key=GEMINI_API_KEY
    )

    result = await orchestrator.process_message(
        message="qual o frete para Avenida Paulista, 1578, São Paulo?",
        personality_prompt="Você é um assistente de delivery."
    )

    # A verificação agora é sobre o resultado final e ignora o separador decimal
    assert result.freight_details is not None
    assert result.freight_details.cost > 0
    # Normaliza a string de resposta para passar no teste independentemente do separador
    response_text_normalized = result.response_text.replace('.', ',')
    assert "R$ 12,50" in response_text_normalized

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY") or not os.getenv("GOOGLE_MAPS_API_KEY"), reason=f"{integration_test_reason} or GOOGLE_MAPS_API_KEY not set")
@pytest.mark.asyncio
async def test_freight_calculation_variable_cost_real_api_call(db_session: Session):
    """
    INTEGRAÇÃO: Verifica o fluxo de cálculo de frete com uma configuração de custo por KM.
    """
    personality_data = schemas.PersonalityCreate(name="variable_freight_personality", prompt="Prompt de teste.")
    db_personality = models.Personality(name=personality_data.name, prompt=personality_data.prompt)
    db_session.add(db_personality)
    db_session.commit()
    db_session.refresh(db_personality)

    variable_tenant_data = schemas.TenantCreate(
        tenant_id="variable_freight_tenant",
        nome_loja="Loja Frete Variável",
        ia_personality=db_personality.name,
        ai_prompt_description="Descrição de teste",
        endereco="Rua Teste, 123",
        cep="12345-678",
        latitude=-23.550520,
        longitude=-46.633308,
        url="http://test.com",
        freight_config='{"type": "PER_KM", "price_per_km": 2.5}'
    )
    variable_tenant = tenant_crud.create_tenant(db_session, variable_tenant_data, "Config AI de teste.")
    
    session_id = "test_real_api_variable_freight"
    logger.info(f"[{session_id}] - INICIO test_freight_calculation_variable_cost_real_api_call")
    orchestrator = OrchestratorAgent(db=db_session, session_id=session_id, tenant_id=variable_tenant.tenant_id, user_id="user_real_api_variable_freight", api_key=GEMINI_API_KEY)
    
    with patch('services.state_manager.state_manager.get_order_state', return_value=OrderState()):
        result = await orchestrator.process_message(
            message="quanto custa a entrega para este local?",
            personality_prompt="Você é um assistente de delivery.",
            client_latitude=-23.561, 
            client_longitude=-46.656  
        )

    print(f"Resposta real da IA (Frete Variável): {result.response_text}")
    assert result.response_text and len(result.response_text) > 0
    assert result.freight_details is not None
    
    assert result.freight_details.cost == pytest.approx(9.53, abs=0.1)
    logger.info(f"[{session_id}] - FIM test_freight_calculation_variable_cost_real_api_call")
