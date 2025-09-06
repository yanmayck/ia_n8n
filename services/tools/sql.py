import json
import logging
import re
from typing import List

from agno.agent import Agent
from agno.tools import tool
from agno.tools.sql import SQLTools
from core.database import DATABASE_URL
from sqlalchemy import text

logger = logging.getLogger(__name__)


class TenantSafeSQLTools(SQLTools):
    def __init__(self, db_url: str, tenant_id: str):
        super().__init__(db_url=db_url)
        self.tenant_id = tenant_id
        logger.info(f"TenantSafeSQLTools inicializada para o tenant: {self.tenant_id}")

    def run_sql_query(self, query: str) -> str:
        if not query.lower().strip().startswith("select"):
            raise ValueError("Only SELECT queries are allowed for security reasons.")

        modified_query = query
        if "where" in query.lower():
            modified_query = f"{query} AND tenant_id = :tenant_id"
        else:
            modified_query = re.sub(
                r'(from\s+[\w".]+)',
                r"\1 WHERE tenant_id = :tenant_id",
                query,
                flags=re.IGNORECASE,
            )

        params = {"tenant_id": self.tenant_id}

        logger.info(
            f"Executing SQL query with tenant filter: {modified_query} with params: {params}"
        )
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(text(modified_query), params)
                rows = result.fetchall()
                if rows:
                    columns = result.keys()
                    formatted_results = [dict(zip(columns, row)) for row in rows]
                    return json.dumps(formatted_results, indent=2, default=str)
                return "No results found."
        except Exception as e:
            logger.error(f"Error executing SQL query: {e}", exc_info=True)
            raise ValueError(f"Error executing SQL query: {e}")


@tool
def get_sql_query_tool(agent: Agent) -> List[TenantSafeSQLTools]:
    """Retorna uma lista de ferramentas SQL seguras para o tenant."""
    tenant_id = agent.session_state.get("tenant_id")
    if not tenant_id:
        raise ValueError(
            "O tenant_id não foi encontrado no estado da sessão do agente."
        )

    return [TenantSafeSQLTools(db_url=DATABASE_URL, tenant_id=tenant_id)]
