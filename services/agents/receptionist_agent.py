import logging
from typing import Union
from sqlalchemy.orm import Session # Adicionado
from agno.models.google import Gemini
from core.schemas import AnaliseDeIntencao, BuscaDeProduto, ModificacaoItem, TarefaIdentificada
from services.agents.base_agent import BaseAgent # Nova importação

logger = logging.getLogger(__name__)

def get_receptionist_agent(model_id: str, api_key: str, db: Session, tenant_id: str, user_id: str, session_id: str):
    return BaseAgent(
        model=Gemini(id=model_id, api_key=api_key),
        api_key=api_key,
        db=db, tenant_id=tenant_id, user_id=user_id, session_id=session_id,
        description=("""
        Você é um especialista em análise de linguagem natural. Sua única função é ler a mensagem do usuário
        e decompor a solicitação em uma ou mais tarefas, retornando um objeto `AnaliseDeIntencao`.

        **REGRAS DE ANÁLISE:**
        1.  **SEMPRE** retorne uma lista de tarefas, mesmo que seja apenas uma.
        2.  **Busca de Produto:** Para qualquer busca de produto (ex: "tem x-bacon sem picles?"), use `tipo_tarefa: 'buscar_produto'`.
            - Os detalhes da busca DEVEM ser colocados como um dicionário no campo `detalhes`.
        3.  **Pedido de Cardápio:** Para pedidos genéricos de cardápio (ex: "cardápio", "menu", "o que tem aí?"), use `tipo_tarefa: 'menu'`.
        4.  **Cálculo de Frete:** Para perguntas sobre entrega, use `tipo_tarefa: 'calcular_frete'`.
        5.  **Outras Tarefas:** Use os tipos de tarefa apropriados como `adicionar_item`, `falar_com_humano`, etc.

        **EXEMPLOS:**
        - "tem pizza de calabresa sem cebola? e qual o frete para a rua X?"
          -> `AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='buscar_produto', detalhes={'termos_gerais': ['pizza de calabresa'], 'ingredientes_excluir': ['cebola']}), TarefaIdentificada(tipo_tarefa='calcular_frete', detalhes='rua X')])`
        - "cardapio"
          -> `AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='menu')])`
        - "quanto custa a entrega?"
          -> `AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='calcular_frete')])`
        """
        ),
        response_model=AnaliseDeIntencao, # <-- AQUI ESTÁ A MUDANÇA PRINCIPAL
        structured_outputs=True,
        session_state={"db": db, "tenant_id": tenant_id},
        add_state_in_messages=True,
        retries=1,
        delay_between_retries=2,
        exponential_backoff=False,
    )
