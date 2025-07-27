import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from crud import product_crud, opcional_crud, promocao_crud
from core import schemas
from api.dependencies import get_db, get_current_user
from services.agent_manager import load_data_to_vector_db
from starlette.concurrency import run_in_threadpool

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Rotas para Produtos ---
@router.post("/products/{tenant_id}", response_model=schemas.Product, tags=["Products"], dependencies=[Depends(get_current_user)])
async def create_product(tenant_id: str, product: schemas.ProductCreate, db: Session = Depends(get_db)):
    logger.info(f"Criando produto para tenant {tenant_id}: {product.nome_produto}")
    db_product = product_crud.create_product(db, product, tenant_id)
    
    return db_product

@router.get("/products/{tenant_id}", response_model=List[schemas.Product], tags=["Products"], dependencies=[Depends(get_current_user)])
def get_products(tenant_id: str, db: Session = Depends(get_db)):
    logger.info(f"Buscando produtos para o tenant: {tenant_id}")
    products = product_crud.get_products_by_tenant(db, tenant_id=tenant_id)
    logger.info(f"Encontrados {len(products)} produtos para o tenant {tenant_id}.")
    # Opcional: Logar os nomes dos produtos para verificação rápida
    if products:
        product_names = [p.nome_produto for p in products]
        logger.debug(f"Nomes dos produtos: {product_names}")
    return products

@router.get("/products/{tenant_id}/{product_id}", response_model=schemas.Product, tags=["Products"], dependencies=[Depends(get_current_user)])
def get_product(tenant_id: str, product_id: int, db: Session = Depends(get_db)):
    logger.info(f"Buscando produto {product_id} para tenant {tenant_id}")
    product = product_crud.get_product(db, product_id)
    if not product or product.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return product

@router.put("/products/{tenant_id}/{product_id}", response_model=schemas.Product, tags=["Products"], dependencies=[Depends(get_current_user)])
async def update_product(tenant_id: str, product_id: int, product: schemas.ProductUpdate, db: Session = Depends(get_db)):
    logger.info(f"Atualizando produto {product_id} para tenant {tenant_id}")
    db_product = product_crud.get_product(db, product_id)
    if not db_product or db_product.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    updated_product = product_crud.update_product(db, product_id, product)
    
    return updated_product

@router.delete("/products/{tenant_id}/{product_id}", tags=["Products"], dependencies=[Depends(get_current_user)])
async def delete_product(tenant_id: str, product_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deletando produto {product_id} para tenant {tenant_id}")
    db_product = product_crud.get_product(db, product_id)
    if not db_product or db_product.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    product_crud.delete_product(db, product_id)
    
    return {"message": "Produto deletado com sucesso."}

# --- Rotas para Ligar/Desligar Opcionais ---
@router.post("/products/{product_id}/opcionais/{opcional_id}", tags=["Products"], dependencies=[Depends(get_current_user)])
def link_opcional_to_product_route(product_id: int, opcional_id: int, db: Session = Depends(get_db)):
    logger.info(f"Ligando opcional {opcional_id} ao produto {product_id}")
    updated_product = product_crud.link_opcional_to_product(db, product_id, opcional_id)
    if not updated_product:
        raise HTTPException(status_code=404, detail="Produto ou opcional não encontrado.")
    return updated_product

@router.delete("/products/{product_id}/opcionais/{opcional_id}", tags=["Products"], dependencies=[Depends(get_current_user)])
def unlink_opcional_from_product_route(product_id: int, opcional_id: int, db: Session = Depends(get_db)):
    logger.info(f"Desligando opcional {opcional_id} do produto {product_id}")
    updated_product = product_crud.unlink_opcional_from_product(db, product_id, opcional_id)
    if not updated_product:
        raise HTTPException(status_code=404, detail="Produto ou opcional não encontrado, ou ligação inexistente.")
    return updated_product

@router.get("/products/{product_id}/opcionais", response_model=List[schemas.Opcional], tags=["Products"], dependencies=[Depends(get_current_user)])
def get_linked_opcionais_route(product_id: int, db: Session = Depends(get_db)):
    logger.info(f"Buscando opcionais ligados ao produto {product_id}")
    opcionais = product_crud.get_linked_opcionais(db, product_id)
    return opcionais