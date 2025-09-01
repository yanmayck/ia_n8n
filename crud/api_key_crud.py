from sqlalchemy.orm import Session
from core import models, schemas
from typing import List

def get_api_keys_for_tenant(db: Session, tenant_id: str):
    return db.query(models.TenantAPIKey).filter(models.TenantAPIKey.tenant_id == tenant_id).order_by(models.TenantAPIKey.priority).all()

def create_tenant_api_key(db: Session, tenant_id: str, key: schemas.TenantAPIKeyCreate):
    db_key = models.TenantAPIKey(**key.dict(), tenant_id=tenant_id)
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    return db_key

def delete_tenant_api_key(db: Session, key_id: int):
    db_key = db.query(models.TenantAPIKey).filter(models.TenantAPIKey.id == key_id).first()
    if db_key:
        db.delete(db_key)
        db.commit()
    return db_key

def replace_all_keys_for_tenant(db: Session, tenant_id: str, keys_data: List[schemas.TenantAPIKeyCreate]):
    """
    Deleta todas as chaves de API existentes de um tenant e insere as novas.
    """
    db.query(models.TenantAPIKey).filter(models.TenantAPIKey.tenant_id == tenant_id).delete(synchronize_session=False)
    
    new_keys = []
    for key_data in keys_data:
        new_key = models.TenantAPIKey(**key_data.dict(), tenant_id=tenant_id)
        new_keys.append(new_key)
        
    db.bulk_save_objects(new_keys)
    db.commit()
