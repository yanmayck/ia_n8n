import logging
import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io
from starlette.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from crud import tenant_crud, product_crud
from core import models, schemas
from services import file_handler, agent_manager
from api.dependencies import get_db, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/tenants/config", response_model=schemas.Tenant, tags=["Tenants"], dependencies=[Depends(get_current_user)])
def get_tenant_config(request: schemas.TenantConfigRequest, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id=request.instancia)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado ou inativo.")
    return tenant

@router.post("/tenant-instancia/", dependencies=[Depends(get_current_user)])
def create_tenant_instancia(tenant_data: schemas.TenantInstancia, db: Session = Depends(get_db)):
    """Endpoint para receber JSON com chave 'instancia'"""
    return tenant_crud.create_tenant_instancia(db, tenant_data)

@router.post("/tenants/", dependencies=[Depends(get_current_user)])
async def create_tenant(
    tenant_id: str = Form(...),
    nome_loja: str = Form(...),
    ia_personality: str = Form(...),
    ai_prompt_description: str = Form(...),
    endereco: str = Form(...),
    cep: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    loja_txt: UploadFile = File(...),
    produtos_excel: UploadFile = File(...),
    menu_image: UploadFile = File(None),
    freight_config: Optional[str] = Form(None), # Novo campo para configuração de frete
    db: Session = Depends(get_db)
):
    conteudo_loja = await loja_txt.read()
    conteudo_loja = conteudo_loja.decode("utf-8")
    
    produtos_content = await produtos_excel.read()
    df = await run_in_threadpool(pd.read_excel, io.BytesIO(produtos_content))
    df.columns = df.columns.str.strip()

    logger.info(f"Colunas lidas do Excel: {df.columns.tolist()}")
    
    tenant_data = schemas.TenantCreate(
        tenant_id=tenant_id,
        nome_loja=nome_loja,
        ia_personality=ia_personality,
        ai_prompt_description=ai_prompt_description,
        endereco=endereco,
        cep=cep,
        latitude=latitude,
        longitude=longitude,
        freight_config=freight_config # Passando o novo campo
    )
    
    menu_image_url = None
    if menu_image:
        try:
            menu_image_url = await file_handler.upload_image_to_supabase(menu_image)
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Erro ao fazer upload da imagem do cardápio para o Supabase: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Erro interno ao fazer upload da imagem do cardápio.")

    tenant = tenant_crud.create_tenant(db, tenant_data, conteudo_loja, menu_image_url)
    
    saved_products = []
    for _, row in df.iterrows():
        produto = models.Product(
            name=row['Plano_(Produto)'],
            price=str(row['Preço_Sugerido_(Mensal)']),
            retrieval_key=row.get('retrieval_key', f"{tenant_id}_{row['Plano_(Produto)']}"),
            tenant_id=tenant_id,
            publico_alvo=row.get('Público-Alvo'),
            principais_funcionalidades=row.get('Principais_Funcionalidades'),
            limitacoes_observacoes=row.get('Limitações/Observações'),
            produto_promocao=row.get('produto_promocao'),
            preco_promotions=row.get('preco_promotions'),
            combo_product=row.get('combo_product')
        )
        db.add(produto)
        saved_products.append(produto)
    db.commit()

    # Carregar dados no PGVector
    await run_in_threadpool(agent_manager.load_data_to_vector_db, tenant_id, conteudo_loja, df)

    return tenant

@router.get("/tenants/", response_model=List[schemas.Tenant], tags=["Tenants"], dependencies=[Depends(get_current_user)])
def get_all_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tenants = tenant_crud.get_all_tenants(db, skip=skip, limit=limit)
    return tenants

@router.get("/tenants/{tenant_id}", response_model=schemas.Tenant, tags=["Tenants"], dependencies=[Depends(get_current_user)])
def get_tenant(tenant_id: str, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return tenant

@router.put("/tenants/{tenant_id}", response_model=schemas.Tenant, tags=["Tenants"], dependencies=[Depends(get_current_user)])
async def update_tenant(
    tenant_id: str,
    nome_loja: Optional[str] = Form(None),
    ia_personality: Optional[str] = Form(None),
    ai_prompt_description: Optional[str] = Form(None),
    endereco: Optional[str] = Form(None),
    cep: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    url: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    freight_config: Optional[str] = Form(None), # Novo campo para configuração de frete
    loja_txt: UploadFile = File(None),
    menu_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    existing_tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
    if not existing_tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    tenant_update_data = {
        "nome_loja": nome_loja,
        "ia_personality": ia_personality,
        "ai_prompt_description": ai_prompt_description,
        "endereco": endereco,
        "cep": cep,
        "latitude": latitude,
        "longitude": longitude,
        "url": url,
        "is_active": is_active,
        "freight_config": freight_config, # Passando o novo campo
    }
    filtered_update_data = {}
    for key, value in tenant_update_data.items():
        if value is not None or (key == "is_active" and value is False):
            filtered_update_data[key] = value

    tenant_update_schema_obj = schemas.TenantUpdateSchema(**filtered_update_data)

    conteudo_loja = None
    if loja_txt:
        conteudo_loja = await loja_txt.read()
        conteudo_loja = conteudo_loja.decode("utf-8")

    menu_image_url_to_update = None
    if menu_image:
        try:
            menu_image_url_to_update = await file_handler.upload_image_to_supabase(menu_image)
            if existing_tenant.menu_image_url:
                await file_handler.delete_image_from_supabase(existing_tenant.menu_image_url)
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Erro ao fazer upload da imagem do cardápio para o Supabase durante atualização: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Erro interno ao fazer upload da imagem do cardápio.")
    
    updated_tenant = tenant_crud.update_tenant(db, tenant_id, tenant_update_schema_obj, conteudo_loja, menu_image_url_to_update)

    

    return updated_tenant

@router.put("/tenants/{tenant_id}/toggle-status", dependencies=[Depends(get_current_user)])
def toggle_tenant_status(tenant_id: str, status_data: dict, db: Session = Depends(get_db)):
    return tenant_crud.toggle_tenant_status(db, tenant_id, status_data["is_active"])

@router.delete("/tenants/{tenant_id}", dependencies=[Depends(get_current_user)])
def delete_tenant(tenant_id: str, db: Session = Depends(get_db)):
    return tenant_crud.delete_tenant(db, tenant_id)

@router.get("/tenant-data/{tenant_id}", dependencies=[Depends(get_current_user)])
def get_tenant_data(tenant_id: str, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    salvar_banco_de_dados_url = "/api/interactions"
    
    return schemas.TenantDataResponse(
        tenantId=tenant.tenant_id,
        ID_pronpt=tenant.id_pronpt,
        url=tenant.url,
        evolutionApiKey=tenant.evolution_api_key,
        isActive=tenant.is_active,
        salvarBancoDeDados=salvar_banco_de_dados_url
    )

@router.post("/tenant-data/", response_model=schemas.TenantDataResponse, dependencies=[Depends(get_current_user)])
def get_tenant_data_by_instancia(request: schemas.TenantDataRequest, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id=request.instancia)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    salvar_banco_de_dados_url = "/api/interactions"
    
    return schemas.TenantDataResponse(
        tenantId=tenant.tenant_id,
        ID_pronpt=tenant.id_pronpt,
        url=tenant.url,
        evolutionApiKey=tenant.evolution_api_key,
        isActive=tenant.is_active,
        salvarBancoDeDados=salvar_banco_de_dados_url
    )

@router.get("/tenants/{tenant_id}/loja_txt", tags=["Tenants"], dependencies=[Depends(get_current_user)])
async def get_loja_txt(tenant_id: str, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant or not tenant.config_ai:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Informações da loja não encontradas.")
    return PlainTextResponse(content=tenant.config_ai, media_type="text/plain")
