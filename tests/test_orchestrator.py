import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session

from services.orchestrator_agent import OrchestratorAgent
from core.schemas import AnaliseDeIntencao, TarefaIdentificada, FinalResponseData, AIResponse
from core.models import Tenant

# Os fixtures 'db_session' e 'test_tenant' são fornecidos pelo conftest.py

@pytest.mark.asyncio
@patch('services.orchestrator_agent.RulesEngine')
@patch('services.orchestrator_agent.VectorDBManager')
@patch('services.orchestrator_agent.Memory')
async def test_orchestrator_routes_to_menu(
    MockMemory, MockVectorDBManager, MockRulesEngine, db_session: Session, test_tenant: Tenant
):
    """
    Testa se o orquestrador direciona corretamente para o 'menu_step'
    quando a intenção do usuário é 'menu'.
    """
    # Configuração
    orchestrator = OrchestratorAgent(db=db_session, session_id="test_session_menu", tenant_id=test_tenant.tenant_id, user_id="user_menu_test")

    # Simula a resposta do agente recepcionista
    receptionist_response = AnaliseDeIntencao(
        tarefas=[TarefaIdentificada(tipo_tarefa="menu", detalhes="O usuário pediu o cardápio")],
        contem_urgencia=False
    )
    
    # Simula a resposta final do agente de formulação de resposta
    final_response = AIResponse(
        response_text="Aqui está o cardápio!",
        human_handoff=False,
        send_menu=True # A flag de enviar menu deve ser True
    )

    # Mock dos agentes e do workflow
    with patch.object(orchestrator.receptionist_agent, 'arun', new_callable=AsyncMock) as mock_receptionist_run, \
         patch.object(orchestrator.menu_agent, 'arun', new_callable=AsyncMock) as mock_menu_run, \
         patch.object(orchestrator.response_formulation_agent, 'arun', new_callable=AsyncMock) as mock_formulation_run:
        
        mock_receptionist_run.return_value.content = receptionist_response
        mock_menu_run.return_value.content = {"should_send_menu": True}
        mock_formulation_run.return_value.content = final_response

        # Execução
        result = await orchestrator.process_message(
            message="qual o cardapio?",
            personality_prompt="test"
        )

        # Verificação
        mock_receptionist_run.assert_called_once() # Garante que o recepcionista foi chamado
        assert result['send_menu'] is True
        assert "Claro! Aqui está o nosso cardápio." in result['response_text']
        assert "Olá! Bem-vindo(a) ao Atendente Virtual da Loja de Teste." in result['response_text']


@pytest.mark.asyncio
@patch('services.orchestrator_agent.RulesEngine')
@patch('services.orchestrator_agent.VectorDBManager')
@patch('services.orchestrator_agent.Memory')
async def test_orchestrator_routes_to_human_handoff(
    MockMemory, MockVectorDBManager, MockRulesEngine, db_session: Session, test_tenant: Tenant
):
    """
    Testa se o orquestrador direciona para o 'human_handoff_step'
    quando a intenção do usuário é 'falar_com_humano'.
    """
    # Configuração
    orchestrator = OrchestratorAgent(db=db_session, session_id="test_session_handoff", tenant_id=test_tenant.tenant_id, user_id="user_handoff_test")

    # Simula a resposta do agente recepcionista
    receptionist_response = AnaliseDeIntencao(
        tarefas=[TarefaIdentificada(tipo_tarefa="falar_com_humano", detalhes="O usuário quer falar com uma pessoa")],
        contem_urgencia=True
    )
    
    final_response = AIResponse(
        response_text="Entendi. Um de nossos atendentes irá continuar a conversa com você em instantes.",
        human_handoff=True, # A flag de handoff deve ser True
        send_menu=False
    )

    # Mock dos agentes
    with patch.object(orchestrator.receptionist_agent, 'arun', new_callable=AsyncMock) as mock_receptionist_run, \
         patch.object(orchestrator.human_handoff_agent, 'arun', new_callable=AsyncMock) as mock_handoff_run, \
         patch.object(orchestrator.response_formulation_agent, 'arun', new_callable=AsyncMock) as mock_formulation_run:

        mock_receptionist_run.return_value.content = receptionist_response
        mock_handoff_run.return_value.content = {"should_handoff": True}
        mock_formulation_run.return_value.content = final_response

        # Execução
        result = await orchestrator.process_message(
            message="quero falar com um atendente",
            personality_prompt="test"
        )

        # Verificação
        mock_receptionist_run.assert_called_once()
        assert result['human_handoff'] is True
        assert "Um de nossos atendentes" in result['response_text']

@pytest.mark.asyncio
@patch('services.orchestrator_agent.RulesEngine')
@patch('services.orchestrator_agent.VectorDBManager')
@patch('services.orchestrator_agent.Memory')
async def test_orchestrator_routes_to_general_question(
    MockMemory, MockVectorDBManager, MockRulesEngine, db_session: Session, test_tenant: Tenant
):
    """
    Testa se o orquestrador usa o 'general_response_agent' para perguntas gerais.
    """
    # Configuração
    orchestrator = OrchestratorAgent(db=db_session, session_id="test_session_general", tenant_id=test_tenant.tenant_id, user_id="user_general_test")

    # Simula a resposta do agente recepcionista
    receptionist_response = AnaliseDeIntencao(
        tarefas=[TarefaIdentificada(tipo_tarefa="fazer_pergunta_geral", detalhes="que horas voces fecham?")],
        contem_urgencia=False
    )
    
    # Simula a resposta do agente de resposta geral
    general_agent_response = FinalResponseData(
        text_response="Nós fechamos às 23h.",
        human_handoff_needed=False,
        send_menu_requested=False
    )

    # Mock dos agentes
    with patch.object(orchestrator.receptionist_agent, 'arun', new_callable=AsyncMock) as mock_receptionist_run, \
         patch.object(orchestrator.response_formulation_agent, 'arun', new_callable=AsyncMock) as mock_formulation_run:

        mock_receptionist_run.return_value.content = receptionist_response
        mock_formulation_run.return_value.content = general_agent_response

        # Execução
        result = await orchestrator.process_message(
            message="que horas voces fecham?",
            personality_prompt="test"
        )

        # Verificação
        mock_receptionist_run.assert_called_once()
        mock_formulation_run.assert_called_once() # Garante que o agente de formulação foi chamado
        assert result['human_handoff'] is False
        assert result['send_menu'] is False
        assert "Nós fechamos às 23h." in result['response_text']
        assert "Olá! Bem-vindo(a) ao Atendente Virtual da Loja de Teste." in result['response_text']
