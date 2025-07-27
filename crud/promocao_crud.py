import logging
from sqlalchemy.orm import Session
from core import models, schemas

logger = logging.getLogger(__name__)

def get_promocao(db: Session, promocao_id: int):
    return db.query(models.Promocao).filter(models.Promocao.id_promocao == promocao_id).first()

def get_promocoes_by_tenant(db: Session, tenant_id: str, skip: int = 0, limit: int = 100):
    return db.query(models.Promocao).filter(models.Promocao.tenant_id == tenant_id).offset(skip).limit(limit).all()

def create_promocao(db: Session, promocao: schemas.PromocaoCreate, tenant_id: str):
    logger.info(f"CRUD: Criando objeto Promocao no modelo para o tenant '{tenant_id}'.")
    db_promocao = models.Promocao(**promocao.model_dump(), tenant_id=tenant_id)
    db.add(db_promocao)
    db.commit()
    db.refresh(db_promocao)
    logger.info(f"CRUD: Promoção '{db_promocao.nome_promocao}' (ID: {db_promocao.id_promocao}) comitada no banco de dados.")
    return db_promocao

def update_promocao(db: Session, promocao_id: int, promocao_data: schemas.PromocaoUpdate):
    db_promocao = get_promocao(db, promocao_id)
    if db_promocao:
        update_data = promocao_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_promocao, key, value)
        db.commit()
        db.refresh(db_promocao)
    return db_promocao

def delete_promocao(db: Session, promocao_id: int):
    db_promocao = get_promocao(db, promocao_id)
    if db_promocao:
        db.delete(db_promocao)
        db.commit()
    return db_promocao