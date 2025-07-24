import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import List
import io
from openpyxl import Workbook
from fastapi.responses import StreamingResponse

from crud import product_crud
from core import schemas
from services import product_service
from api.dependencies import get_db, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload-products", tags=["Products"], dependencies=[Depends(get_current_user)])
async def upload_products(tenant_id: str, file: UploadFile, db: Session = Depends(get_db)):
    logger.info(f"Iniciando upload de produtos para tenant: {tenant_id}")
    try:
        products = await product_service.process_product_sheet(tenant_id, file, db)
        logger.info(f"{len(products)} produtos uploaded successfully for tenant: {tenant_id}")
        return {"message": f"{len(products)} products uploaded successfully."}
    except Exception as e:
        logger.error(f"Erro no upload de produtos para tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/products/{tenant_id}", response_model=List[schemas.Product], tags=["Products"], dependencies=[Depends(get_current_user)])
def get_products(tenant_id: str, db: Session = Depends(get_db)):
    logger.info(f"Buscando produtos para tenant: {tenant_id}")
    return product_crud.get_products_by_tenant_id(db, tenant_id=tenant_id)

@router.get("/products/{tenant_id}/download-excel", tags=["Products"], dependencies=[Depends(get_current_user)])
async def download_products_excel(tenant_id: str, db: Session = Depends(get_db)):
    logger.info(f"Gerando arquivo Excel de produtos para tenant: {tenant_id}")
    products = product_crud.get_products_by_tenant_id(db, tenant_id=tenant_id)
    
    if not products:
        raise HTTPException(status_code=404, detail="Nenhum produto encontrado para este cliente.")

    wb = Workbook()
    ws = wb.active
    ws.title = "Produtos"

    headers = [
        "Plano_(Produto)", 
        "Preço_Sugerido_(Mensal)", 
        "retrieval_key", 
        "tenant_id", 
        "Público-Alvo", 
        "Principais_Funcionalidades", 
        "Limitações/Observações", 
        "produto_promocao", 
        "preco_promotions", 
        "combo_product",
        "tempo_preparo_minutos"
    ]
    ws.append(headers)

    for product in products:
        ws.append([
            product.name,
            product.price,
            product.retrieval_key,
            product.tenant_id,
            product.publico_alvo,
            product.principais_funcionalidades,
            product.limitacoes_observacoes,
            product.produto_promocao,
            product.preco_promotions,
            product.combo_product,
            product.tempo_preparo_minutos
        ])

    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    filename = f"produtos_{tenant_id}.xlsx"
    return StreamingResponse(excel_file, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/get-file/{retrieval_key}", tags=["Files"], dependencies=[Depends(get_current_user)])
def get_file(retrieval_key: str, db: Session = Depends(get_db)):
    logger.info(f"Requisição para recuperar informações do produto com retrieval_key: {retrieval_key}")
    product = product_crud.get_product_by_retrieval_key(db, retrieval_key=retrieval_key)

    if not product:
        logger.warning(f"Produto não encontrado para retrieval_key: {retrieval_key}")
        raise HTTPException(status_code=404, detail="Produto não encontrado com esta chave.")

    logger.info(f"Produto '{product.name}' encontrado para retrieval_key: {retrieval_key}")
    # Este endpoint atualmente apenas confirma a existência do produto.
    # Para servir o conteúdo de um arquivo real, seria necessário um mecanismo de armazenamento de arquivos.
    return {"message": f"Informações do produto para a chave '{retrieval_key}' recuperadas com sucesso.", "product_name": product.name, "product_details": product.dict()}
