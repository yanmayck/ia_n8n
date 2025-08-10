import logging
from typing import Union
from sqlalchemy.orm import Session # Adicionado
from agno.agent import Agent
from agno.models.google import Gemini
from core.schemas import AnaliseDeIntencao, BuscaDeProduto, ModificacaoItem, TarefaIdentificada

logger = logging.getLogger(__name__)

def get_receptionist_agent(model_id: str, api_key: str, db: Session, tenant_id: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key),
        description="""
        Você é um especialista em análise de linguagem natural. Sua única função é ler a mensagem do usuário
        e decompor a solicitação em uma estrutura JSON. Use o schema `BuscaDeProduto` se a intenção principal
        for encontrar ou modificar um produto. Use o schema `AnaliseDeIntencao` para outras intenções.

        **REGRA CRÍTICA PARA FRETE:** Para **QUALQUER** pergunta sobre custo de entrega, valor da entrega, cálculo de frete, ou similar,
        você **DEVE OBRIGATORIAMENTE** usar o `tipo_tarefa` como `'calcular_frete'`.

        Exemplos de `BuscaDeProduto`:
        - "Quero um x-bacon sem picles" -> BuscaDeProduto(termos_gerais=["x-bacon"], modificacoes=[ModificacaoItem(tipo='REMOVER_INGREDIENTE', nome_item='picles')])
        - "tem pizza de calabresa?" -> BuscaDeProduto(termos_gerais=["pizza de calabresa"])
        - "o que tem de sobremesa?" -> BuscaDeProduto(categorias=["sobremesas"])

        Exemplos de `AnaliseDeIntencao`:
        - "quanto é a entrega?" -> AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='calcular_frete')])
        - "qual o valor do frete?" -> AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='calcular_frete')])
        - "cardapio" -> AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='menu')])
        - "falar com atendente" -> AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='falar_com_humano')])
        - "Eu quero duas pizzas de calabresa e uma coca-cola." -> AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='adicionar_item', detalhes='duas pizzas de calabresa e uma coca-cola')])
        """,
        response_model=Union[BuscaDeProduto, AnaliseDeIntencao], # A IA pode escolher qual schema retornar
        structured_outputs=True,
        session_state={"db": db, "tenant_id": tenant_id},
        add_state_in_messages=True,
        retries=1,
        delay_between_retries=2,
        exponential_backoff=False,
    )
