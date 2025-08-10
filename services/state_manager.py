import redis
import os
import json
import logging
from typing import Optional, Dict, Any

from core.schemas import OrderState

logger = logging.getLogger(__name__)

class RedisStateManager:
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                decode_responses=True # Decodifica as respostas de bytes para string
            )
            self.redis_client.ping() # Verifica a conexão
            logger.info(f"Conectado com sucesso ao Redis em {self.redis_host}:{self.redis_port}")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Não foi possível conectar ao Redis: {e}", exc_info=True)
            raise

    def get_order_state(self, session_id: str) -> Optional[OrderState]:
        """Recupera o estado do pedido do Redis."""
        try:
            state_json = self.redis_client.get(session_id)
            if state_json:
                state_dict = json.loads(state_json)
                logger.debug(f"Estado recuperado para a sessão {session_id}: {state_dict}")
                return OrderState(**state_dict)
            return None
        except Exception as e:
            logger.error(f"Erro ao recuperar estado para a sessão {session_id}: {e}", exc_info=True)
            return None

    def save_order_state(self, session_id: str, state: OrderState, ttl: int = 86400):
        """Salva o estado do pedido no Redis com um TTL (Time To Live) de 24 horas."""
        try:
            state_json = state.model_dump_json()
            self.redis_client.set(session_id, state_json, ex=ttl)
            logger.debug(f"Estado salvo para a sessão {session_id}: {state_json}")
        except Exception as e:
            logger.error(f"Erro ao salvar estado para a sessão {session_id}: {e}", exc_info=True)

# Instância única para ser usada em toda a aplicação
state_manager = RedisStateManager()
