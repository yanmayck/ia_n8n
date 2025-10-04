import logging

from agno.models.google import Gemini
from core.schemas import AnaliseDeIntencao
from sqlalchemy.orm import Session  # Adicionado

from services.agents.base_agent import BaseAgent  # Nova importação

logger = logging.getLogger(__name__)


def get_receptionist_agent(
    model_id: str,
    api_key: str,
    db: Session,
    tenant_id: str,
    user_id: str,
    session_id: str,
):
    return BaseAgent(
        model=Gemini(id=model_id, api_key=api_key),
        api_key=api_key,
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        description=(
            """
        Você é um especialista em análise de linguagem natural. Sua única função é ler a mensagem do usuário
        e o histórico da conversa para decompor a solicitação em uma ou mais tarefas, retornando um objeto `AnaliseDeIntencao`.

        **REGRAS DE ANÁLISE:**
        1.  **Use o histórico para contexto SEMPRE.** A ação correta muitas vezes depende da pergunta anterior da IA.
        2.  **Saudação Simples:** Se a mensagem for apenas uma saudação (ex: "oi", "bom dia"), use `tipo_tarefa: 'saudacao'`.
        3.  **Finalizar Pedido:** Se o usuário indicar que quer finalizar o pedido (ex: "pode fechar a conta", "só isso", "finalizar pedido"), use `tipo_tarefa: 'fechar_conta'`.
        4.  **Adicionar Item vs. Buscar Produto:**
            - Se a IA perguntou o que o cliente deseja (ex: "Como posso te ajudar?", "Algo mais?") e o cliente responde com um item (ex: "gostaria de uma pizza", "tem x-bacon?"), a tarefa é `adicionar_item`.
            - Se o cliente faz uma pergunta sobre um item sem um convite prévio da IA, geralmente é uma `buscar_produto`.
        5.  **Aceite de Oferta:** Se a IA acabou de oferecer algo (uma promoção, um item) e o usuário aceitar (ex: "sim, pode adicionar", "quero sim"), use `tipo_tarefa: 'aceitar_oferta'`.
        6.  **Confirmação de Pedido:** Para confirmações de finalização (ex: "sim, pode confirmar", "isso mesmo"), use `tipo_tarefa: 'confirmar_pedido'`.
        7.  **Informar Endereço:** Se o usuário informar um endereço (ex: "entregar na Rua das Flores, 123"), use `tipo_tarefa: 'calcular_frete'` e coloque o endereço completo no campo `detalhes`.
        8.  **Informar Pagamento:** Se o usuário informar a forma de pagamento (ex: "vou pagar com pix", "é cartão"), use `tipo_tarefa: 'informar_metodo_pagamento'` e coloque o método (ex: 'pix', 'cartao', 'dinheiro') no campo `detalhes`.
        9.  **Mensagens Combinadas:** Se uma mensagem contiver múltiplas informações (ex: endereço e pagamento), crie uma tarefa para cada uma.
        10. **Outras Tarefas:** Use `menu`, `remover_item`, `falar_com_humano` conforme necessário.
        11. **SEMPRE** retorne uma lista de tarefas.

        **EXEMPLOS:**
         - Histórico: [IA: "Como posso te ajudar?"], Usuário: "gostaria de uma pizza de calabresa"                                    
        -> `AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='adicionar_item', detalhes='pizza de calabresa')])`          
          Histórico: [], Usuário: "vcs tem pizza de calabresa?"                                                                     
         -> `AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='buscar_produto', detalhes={'termos_gerais': ['pizza de calabresa']})])                          
        - Histórico: [IA: "Algo mais?"], Usuário: "só isso, pode fechar a conta"
          -> `AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='fechar_conta')])`
        - Histórico: [IA: "Qual a forma de pagamento?"], Usuário: "cartão. o endereço é rua das flores, 123"
          -> `AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='informar_metodo_pagamento', detalhes='cartao'), TarefaIdentificada(tipo_tarefa='calcular_frete', detalhes='Rua das Flores, 123')])`
        - Histórico: [IA: "Temos uma promoção de borda recheada. Deseja adicionar?"], Usuário: "sim, por favor"
          -> `AnaliseDeIntencao(tarefas=[TarefaIdentificada(tipo_tarefa='aceitar_oferta')])`
        """
        ),
        response_model=AnaliseDeIntencao,
        structured_outputs=True,
        add_history_to_messages=True,  # <-- Habilita a memória
        num_history_runs=2,  # <-- Define o tamanho da memória
        session_state={"db": db, "tenant_id": tenant_id},
        add_state_in_messages=True,
        retries=1,
        delay_between_retries=2,
        exponential_backoff=False,
    )
