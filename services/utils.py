import time
import logging
from functools import wraps
from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)

def retry_with_exponential_backoff(
    initial_delay: float = 2,
    exponential_base: float = 2,
    max_retries: int = 5,
    errors: tuple = (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable),
):
    """
    Decorador que implementa uma política de retentativa com espera exponencial
    para chamadas de função que podem falhar devido a erros transitórios da API.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            for i in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except errors as e:
                    logger.warning(
                        f"API error '{type(e).__name__}' na chamada de '{func.__name__}'. "
                        f"Tentativa {i + 1} de {max_retries}. "
                        f"Esperando {delay:.2f}s antes de tentar novamente."
                    )
                    time.sleep(delay)
                    delay *= exponential_base
            
            logger.error(f"Falha na chamada de '{func.__name__}' após {max_retries} tentativas.")
            raise Exception(f"A função {func.__name__} falhou após {max_retries} tentativas.")

        return wrapper
    return decorator
