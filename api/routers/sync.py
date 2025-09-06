import logging
import os

from api.dependencies import get_db
from core import schemas
from crud import (
    api_key_crud,
    menu_image_crud,
    opcional_crud,
    product_crud,
    promocao_crud,
    tenant_crud,
)
from fastapi import APIRouter, Depends, Header, HTTPException, status
from services import data_sync_service
from sqlalchemy.orm import Session

router = APIRouter()
logger = logging.getLogger(__name__)

# Pega o segredo compartilhado do ambiente para validar o webhook
SYNC_SECRET = os.getenv("SYNC_SECRET_KEY")


def verify_sync_secret(x_sync_secret: str = Header(None)):
    if not SYNC_SECRET:
        logger.error(
            "A chave secreta de sincronização (SYNC_SECRET_KEY) não está configurada no servidor ia_n8n."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Serviço de sincronização não configurado.",
        )
    if not x_sync_secret or x_sync_secret != SYNC_SECRET:
        logger.warning(
            "Tentativa de acesso ao webhook de sincronização com segredo inválido."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Segredo de sincronização inválido ou ausente.",
        )


@router.post("/sync/webhook", tags=["Sync"], dependencies=[Depends(verify_sync_secret)])
async def sync_webhook_receiver(
    payload: schemas.WebhookPayload, db: Session = Depends(get_db)
):
    """
    Recebe um pacote completo de dados do dashboard e sincroniza o estado do tenant no ia_n8n.
    """
    tenant_data = payload.tenant_data
    tenant_id = tenant_data.id

    logger.info(
        f"Webhook de sincronização recebido para o tenant_id: {tenant_id}. Evento: {payload.event_type}"
    )

    try:
        # 1. Sincronizar dados básicos do Tenant e da Personalidade
        db_tenant = tenant_crud.get_tenant_by_id(db, tenant_id)

        # A lógica de personalidade agora é tratada dentro das funções CRUD
        if db_tenant:
            logger.info(f"Atualizando tenant existente: {tenant_id}")
            # Cria o schema de atualização a partir dos dados recebidos
            update_schema = schemas.TenantUpdateSchema(
                nome_loja=tenant_data.nome_loja,
                ia_personality=tenant_data.ia_personality,
                ai_prompt_description=tenant_data.ai_prompt_description,
                endereco=tenant_data.endereco,
                cep=tenant_data.cep,
                latitude=tenant_data.latitude,
                longitude=tenant_data.longitude,
                url=tenant_data.url,
                is_active=tenant_data.is_active,
                freight_config=tenant_data.freight_config,
            )
            tenant_crud.update_tenant(
                db, tenant_id, update_schema, tenant_data.config_ai
            )
        else:
            logger.info(f"Criando novo tenant: {tenant_id}")
            # O objeto tenant_data (WebhookTenantData) é compatível com TenantCreate
            tenant_crud.create_tenant(
                db,
                tenant_data,
                tenant_data.config_ai,
                tenant_data.evolution_instance_name,
            )

        # 2. Sincronizar Chaves de API (Gemini)
        api_key_crud.replace_all_keys_for_tenant(db, tenant_id, tenant_data.api_keys)
        logger.info(f"Chaves de API sincronizadas para o tenant: {tenant_id}")

        # 3. Sincronizar Cardápio Completo
        menu = tenant_data.menu
        product_crud.replace_all_products_for_tenant(db, tenant_id, menu.produtos)
        opcional_crud.replace_all_opcionais_for_tenant(db, tenant_id, menu.opcionais)
        promocao_crud.replace_all_promocoes_for_tenant(db, tenant_id, menu.promocoes)
        menu_image_crud.replace_all_images_for_tenant(db, tenant_id, menu.imagens)
        logger.info(
            f"Cardápio (produtos, opcionais, promoções, imagens) sincronizado para o tenant: {tenant_id}"
        )

        # 4. Re-vetorizar todos os dados para a IA
        await data_sync_service.load_data_to_vector_db(db, tenant_id)
        logger.info(f"Dados do tenant {tenant_id} re-vetorizados com sucesso.")

        return {
            "status": "success",
            "message": f"Tenant {tenant_id} sincronizado com sucesso.",
        }

    except Exception as e:
        logger.critical(
            f"Erro CRÍTICO durante a sincronização via webhook para o tenant {tenant_id}: {e}",
            exc_info=True,
        )
        # Em um cenário de produção, poderia haver uma fila de retentativa aqui.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro interno durante a sincronização: {e}",
        )
