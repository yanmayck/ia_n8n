import logging
from agno.agent import Agent
from agno.models.google import Gemini
from core.schemas import AnaliseDeIntencao

logger = logging.getLogger(__name__)

def get_receptionist_agent(model_id: str, api_key: str):
    return Agent(
        model=Gemini(id=model_id, api_key=api_key),
        description="""
        Você é um especialista em análise de linguagem natural. Sua única função é ler a mensagem do usuário
        e decompor todas as solicitações em uma lista de tarefas estruturadas. Preencha o formulário JSON
        (AnaliseDeIntencao) com base na mensagem. Se o usuário pedir mais de uma coisa, adicione cada uma
        como um item separado na lista 'tarefas'.

        Exemplos de tipo_tarefa:
        - 'adicionar_item': Quando o usuário pede um produto ou item para o pedido.
        - 'verificar_promocao': Quando o usuário pergunta sobre promoções.
        - 'fazer_pergunta_geral': Para perguntas que não se encaixam nas outras categorias.
        - 'falar_com_humano': Se o usuário pedir para falar com uma pessoa.
        - 'menu': Se o usuário pedir o cardápio.
        - 'frete': Se o usuário perguntar sobre frete.
        """,
        response_model=AnaliseDeIntencao,
        structured_outputs=True,
    )
