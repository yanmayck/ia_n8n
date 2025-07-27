import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from crud import opcional_crud
from core import schemas
from api.dependencies import get_db, get_current_user
from services.agent_manager import load_data_to_vector_db
from starlette.concurrency import run_in_threadpool

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/opcionais/{tenant_id}", response_model=schemas.Opcional, tags=["Opcionais"], dependencies=[Depends(get_current_user)])
async def create_opcional(tenant_id: str, opcional: schemas.OpcionalCreate, db: Session = Depends(get_db)):
    logger.info(f"Criando opcional para tenant {tenant_id}: {opcional.nome_opcional}")
    db_opcional = opcional_crud.create_opcional(db, opcional, tenant_id)
    
    return db_opcional

@router.get("/opcionais/{tenant_id}", response_model=List[schemas.Opcional], tags=["Opcionais"], dependencies=[Depends(get_current_user)])
def get_opcionais(tenant_id: str, db: Session = Depends(get_db)):
    logger.info(f"Buscando opcionais para o tenant: {tenant_id}")
    opcionais = opcional_crud.get_opcionais_by_tenant(db, tenant_id)
    logger.info(f"Encontrados {len(opcionais)} opcionais para o tenant {tenant_id}.")
    return opcionais

@router.put("/opcionais/{tenant_id}/{opcional_id}", response_model=schemas.Opcional, tags=["Opcionais"], dependencies=[Depends(get_current_user)])
async def update_opcional(tenant_id: str, opcional_id: int, opcional: schemas.OpcionalUpdate, db: Session = Depends(get_db)):
    logger.info(f"Atualizando opcional {opcional_id} para tenant {tenant_id}")
    db_opcional = opcional_crud.get_opcional(db, opcional_id)
    if not db_opcional or db_opcional.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Opcional não encontrado.")
    
    updated_opcional = opcional_crud.update_opcional(db, opcional_id, opcional)
    
    return updated_opcional

@router.delete("/opcionais/{tenant_id}/{opcional_id}", tags=["Opcionais"], dependencies=[Depends(get_current_user)])
async def delete_opcional(tenant_id: str, opcional_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deletando opcional {opcional_id} para tenant {tenant_id}")
    db_opcional = opcional_crud.get_opcional(db, opcional_id)
    if not db_opcional or db_opcional.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Opcional não encontrado.")
    
    opcional_crud.delete_opcional(db, opcional_id)
    
    return {"message": "Opcional deletado com sucesso."}