import logging
from typing import List, Dict, Optional
import httpx
from sqlalchemy.orm import Session
from crud import tenant_crud

logger = logging.getLogger(__name__)

async def save_order_to_platform(user_id: str, tenant_id: str, items: List[Dict], total_price: float, db: Session, address: Optional[str] = None, freight_details: Optional[Dict] = None):
    """
    Envia o pedido confirmado para a plataforma de gestão.
    """
    try:
        tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
        if not tenant or not tenant.url:
            logger.error(f"URL da plataforma de gestão não configurada para o tenant {tenant_id}")
            return

        order_data = {
            "cliente_contato": user_id,
            "valor_total": total_price,
            "observacoes": "Pedido via IA",
            "itens_pedido": items,
            "endereco": address,
            "freight_details": freight_details
        }

        platform_url = f"{tenant.url}/api/pedidos"

        async with httpx.AsyncClient() as client:
            # Idealmente, a chamada para a outra API também seria autenticada.
            response = await client.post(platform_url, json=order_data)
            response.raise_for_status()
            logger.info(f"Pedido para o tenant {tenant_id} enviado com sucesso para a plataforma de gestão.")

    except httpx.RequestError as exc:
        logger.error(f"Erro ao enviar pedido para a plataforma de gestão: {exc}")
    except Exception as e:
        logger.error(f"Erro inesperado ao enviar pedido: {e}", exc_info=True)
