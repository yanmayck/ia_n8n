import logging
import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io
from starlette.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from crud import tenant_crud, product_crud, opcional_crud, promocao_crud, menu_image_crud
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
    freight_config: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    conteudo_loja = await loja_txt.read()
    conteudo_loja = conteudo_loja.decode("utf-8")
    
    tenant_data = schemas.TenantCreate(
        tenant_id=tenant_id,
        nome_loja=nome_loja,
        ia_personality=ia_personality,
        ai_prompt_description=ai_prompt_description,
        endereco=endereco,
        cep=cep,
        latitude=latitude,
        longitude=longitude,
        freight_config=freight_config
    )
    
    tenant = tenant_crud.create_tenant(db, tenant_data, conteudo_loja)
    
    # Carregar dados no PGVector (agora sem o df de produtos)
    await agent_manager.load_data_to_vector_db(db, tenant_id)

    return tenant

@router.get("/tenants/", response_model=List[schemas.Tenant], tags=["Tenants"], dependencies=[Depends(get_current_user)])
def get_all_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        tenants = tenant_crud.get_all_tenants(db, skip=skip, limit=limit)
        logger.info(f"Clientes recuperados do banco de dados: {tenants}")
        return tenants
    except Exception as e:
        logger.error(f"Erro ao buscar clientes no banco de dados: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao buscar informações dos clientes."
        )

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
    freight_config: Optional[str] = Form(None),
    loja_txt: UploadFile = File(None),
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
        "freight_config": freight_config,
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

    updated_tenant = tenant_crud.update_tenant(db, tenant_id, tenant_update_schema_obj, conteudo_loja)

    # Re-carregar dados no PGVector após atualização
    await agent_manager.load_data_to_vector_db(db, tenant_id)

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

# --- Rotas para Imagens de Cardápio ---
from typing import List

@router.post("/tenants/{tenant_id}/menu-images/", response_model=List[schemas.MenuImage], tags=["Tenants"], dependencies=[Depends(get_current_user)])
async def upload_menu_images(tenant_id: str, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    
    uploaded_images = []
    for file in files:
        image_url = await file_handler.upload_image_to_supabase(file)
        menu_image_data = schemas.MenuImageCreate(image_url=image_url, description=file.filename)
        db_menu_image = menu_image_crud.create_menu_image(db, menu_image_data, tenant_id)
        uploaded_images.append(db_menu_image)
        
    return uploaded_images

@router.get("/tenants/{tenant_id}/menu-images/", response_model=List[schemas.MenuImage], tags=["Tenants"], dependencies=[Depends(get_current_user)])
def get_menu_images(tenant_id: str, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    return menu_image_crud.get_menu_images_by_tenant(db, tenant_id)

@router.delete("/tenants/{tenant_id}/menu-images/{image_id}", tags=["Tenants"], dependencies=[Depends(get_current_user)])
async def delete_menu_image(tenant_id: str, image_id: int, db: Session = Depends(get_db)):
    db_menu_image = menu_image_crud.get_menu_image_by_id(db, image_id)
    if not db_menu_image or db_menu_image.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Imagem não encontrada para este tenant.")
    
    await file_handler.delete_image_from_supabase(db_menu_image.image_url)
    menu_image_crud.delete_menu_image(db, image_id)
    return {"message": "Imagem deletada com sucesso."}