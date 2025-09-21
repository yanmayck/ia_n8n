import logging
import os
from typing import Dict, List, Optional

import httpx
from crud import tenant_crud
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Leia a chave secreta do ambiente
SYNC_SECRET_KEY = os.getenv("SYNC_SECRET_KEY")


async def save_order_to_platform(
    user_id: str,
    tenant_id: str,
    items: List[Dict],
    total_price: float,
    db: Session,
    address: Optional[str] = None,
    freight_details: Optional[Dict] = None,
    payment_method: Optional[str] = None,
):
    """
    Envia o pedido confirmado para a plataforma de gestão, formatando os itens para o formato esperado.
    """
    if not SYNC_SECRET_KEY:
        logger.error(
            "SYNC_SECRET_KEY não configurada no ambiente do ia_n8n. Não é possível enviar o pedido."
        )
        # Levanta uma exceção para interromper o fluxo
        raise ValueError("Chave de sincronização não configurada no serviço de IA.")

    try:
        tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
        if not tenant or not tenant.url:
            logger.error(
                f"URL da plataforma de gestão não configurada para o tenant {tenant_id}"
            )
            return

        itens_para_plataforma = [
            {"produto_id": item.get("product_id"), "quantidade": item.get("quantity")}
            for item in items
        ]

        order_data = {
            "tenant_id": tenant_id,  # Adiciona o tenant_id ao corpo
            "cliente_contato": user_id,
            "observacoes": "Pedido via IA",
            "itens_pedido": itens_para_plataforma,
            "endereco": address,
            "freight_details": freight_details,
            "payment_method": payment_method,
        }

        platform_url = f"{tenant.url}/api/pedidos"

        # Cria o cabeçalho de autenticação
        headers = {"X-Sync-Secret": SYNC_SECRET_KEY}

        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Adiciona o cabeçalho à requisição
            response = await client.post(platform_url, json=order_data, headers=headers)
            response.raise_for_status()
            logger.info(
                f"Pedido para o tenant {tenant_id} enviado com sucesso para a plataforma de gestão."
            )

    except httpx.RequestError as exc:
        logger.error(f"Erro ao enviar pedido para a plataforma de gestão: {exc}")
        # Re-raise a exceção para que o orquestrador saiba que falhou
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao enviar pedido: {e}", exc_info=True)
        # Re-raise a exceção
        raise
