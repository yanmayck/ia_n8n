import logging
from typing import List

from core import models, schemas
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def get_opcional(db: Session, opcional_id: int):
    return (
        db.query(models.Opcional)
        .filter(models.Opcional.id_opcional == opcional_id)
        .first()
    )


def get_opcionais_by_tenant(
    db: Session, tenant_id: str, skip: int = 0, limit: int = 100
):
    return (
        db.query(models.Opcional)
        .filter(models.Opcional.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_opcional(db: Session, opcional: schemas.OpcionalCreate, tenant_id: str):
    logger.info(f"CRUD: Criando objeto Opcional no modelo para o tenant '{tenant_id}'.")
    db_opcional = models.Opcional(**opcional.model_dump(), tenant_id=tenant_id)
    db.add(db_opcional)
    db.commit()
    db.refresh(db_opcional)
    logger.info(
        f"CRUD: Opcional '{db_opcional.nome_opcional}' (ID: {db_opcional.id_opcional}) comitado no banco de dados."
    )
    return db_opcional


def update_opcional(
    db: Session, opcional_id: int, opcional_data: schemas.OpcionalUpdate
):
    db_opcional = get_opcional(db, opcional_id)
    if db_opcional:
        update_data = opcional_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_opcional, key, value)
        db.commit()
        db.refresh(db_opcional)
    return db_opcional


def delete_opcional(db: Session, opcional_id: int):
    db_opcional = get_opcional(db, opcional_id)
    if db_opcional:
        db.delete(db_opcional)
        db.commit()
    return db_opcional


def replace_all_opcionais_for_tenant(
    db: Session, tenant_id: str, opcionais_data: List[schemas.OpcionalCreate]
):
    """
    Deleta todos os opcionais existentes de um tenant e insere os novos.
    """
    db.query(models.Opcional).filter(models.Opcional.tenant_id == tenant_id).delete(
        synchronize_session=False
    )

    new_opcionais = []
    for opc_data in opcionais_data:
        new_opc = models.Opcional(
            tenant_id=tenant_id,
            nome_opcional=opc_data.nome_opcional,
            tipo_opcional=opc_data.tipo_opcional,
            preco_adicional=opc_data.preco_adicional,
        )
        new_opcionais.append(new_opc)

    if new_opcionais:
        db.bulk_save_objects(new_opcionais)

    db.commit()
