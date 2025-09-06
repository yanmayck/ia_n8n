import logging

from agno.tools import tool
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


@tool
def search_tool(query: str) -> str:
    """Realiza uma pesquisa na web."""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            return str(results) if results else "Nenhum resultado encontrado."
    except Exception as e:
        logger.error(f"Erro na ferramenta de busca: {e}")
        return "Ocorreu um erro ao pesquisar."
