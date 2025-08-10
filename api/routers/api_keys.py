import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from crud import api_key_crud, tenant_crud
from core import schemas
from api.dependencies import get_db, get_current_user

router = APIRouter(
    prefix="/tenants/{tenant_id}/keys",
    tags=["API Keys"],
    dependencies=[Depends(get_current_user)]
)
logger = logging.getLogger(__name__)

@router.post("/", response_model=schemas.TenantAPIKey)
def create_api_key_for_tenant(tenant_id: str, key: schemas.TenantAPIKeyCreate, db: Session = Depends(get_db)):
    db_tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    logger.info(f"Criando chave API do tipo '{key.key_type}' para o tenant {tenant_id}")
    return api_key_crud.create_tenant_api_key(db, tenant_id=tenant_id, key=key)

@router.get("/", response_model=List[schemas.TenantAPIKey])
def get_tenant_api_keys(tenant_id: str, db: Session = Depends(get_db)):
    db_tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    return api_key_crud.get_api_keys_for_tenant(db, tenant_id=tenant_id)

@router.delete("/{key_id}")
def delete_tenant_api_key(tenant_id: str, key_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deletando chave API ID {key_id} do tenant {tenant_id}")
    deleted_key = api_key_crud.delete_tenant_api_key(db, key_id=key_id)
    if not deleted_key:
        raise HTTPException(status_code=404, detail="Chave de API não encontrada.")
    return {"message": "Chave de API deletada com sucesso."}
