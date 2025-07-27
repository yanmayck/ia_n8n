import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from crud import promocao_crud
from core import schemas
from api.dependencies import get_db, get_current_user
from services.agent_manager import load_data_to_vector_db
from starlette.concurrency import run_in_threadpool

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/promocoes/{tenant_id}", response_model=schemas.Promocao, tags=["Promocoes"], dependencies=[Depends(get_current_user)])
async def create_promocao(tenant_id: str, promocao: schemas.PromocaoCreate, db: Session = Depends(get_db)):
    logger.info(f"Criando promoção para tenant {tenant_id}: {promocao.nome_promocao}")
    db_promocao = promocao_crud.create_promocao(db, promocao, tenant_id)
    
    return db_promocao

@router.get("/promocoes/{tenant_id}", response_model=List[schemas.Promocao], tags=["Promocoes"], dependencies=[Depends(get_current_user)])
def get_promocoes(tenant_id: str, db: Session = Depends(get_db)):
    logger.info(f"Buscando promoções para o tenant: {tenant_id}")
    promocoes = promocao_crud.get_promocoes_by_tenant(db, tenant_id)
    logger.info(f"Encontradas {len(promocoes)} promoções para o tenant {tenant_id}.")
    return promocoes

@router.put("/promocoes/{tenant_id}/{promocao_id}", response_model=schemas.Promocao, tags=["Promocoes"], dependencies=[Depends(get_current_user)])
async def update_promocao(tenant_id: str, promocao_id: int, promocao: schemas.PromocaoUpdate, db: Session = Depends(get_db)):
    logger.info(f"Atualizando promoção {promocao_id} para tenant {tenant_id}")
    db_promocao = promocao_crud.get_promocao(db, promocao_id)
    if not db_promocao or db_promocao.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Promoção não encontrada.")
    
    updated_promocao = promocao_crud.update_promocao(db, promocao_id, promocao)
    
    return updated_promocao

@router.delete("/promocoes/{tenant_id}/{promocao_id}", tags=["Promocoes"], dependencies=[Depends(get_current_user)])
async def delete_promocao(tenant_id: str, promocao_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deletando promoção {promocao_id} para tenant {tenant_id}")
    db_promocao = promocao_crud.get_promocao(db, promocao_id)
    if not db_promocao or db_promocao.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Promoção não encontrada.")
    
    promocao_crud.delete_promocao(db, promocao_id)
    
    return {"message": "Promoção deletada com sucesso."}