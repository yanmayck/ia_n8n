import logging
from typing import List, Optional

import httpx
from api.dependencies import get_current_user, get_db
from core import schemas
from crud import (
    menu_image_crud,
    opcional_crud,
    product_crud,
    promocao_crud,
    tenant_crud,
)
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from services import data_sync_service
from services.integrations import supabase_client
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/tenants/config",
    response_model=schemas.Tenant,
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
def get_tenant_config(
    request: schemas.TenantConfigRequest, db: Session = Depends(get_db)
):
    # Altera a busca para usar o nome da instância em vez do ID do tenant
    tenant = tenant_crud.get_tenant_by_instance_name(
        db, instance_name=request.instancia
    )
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado ou inativo para a instância fornecida.",
        )
    return tenant


@router.post("/tenant-instancia/", dependencies=[Depends(get_current_user)])
def create_tenant_instancia(
    tenant_data: schemas.TenantInstancia, db: Session = Depends(get_db)
):
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
    db: Session = Depends(get_db),
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
        freight_config=freight_config,
    )

    tenant = None
    try:
        logger.info(f"Iniciando criação do tenant: {tenant_id}")
        tenant = tenant_crud.create_tenant(db, tenant_data, conteudo_loja)
        logger.info(
            f"Tenant {tenant_id} criado no banco de dados, iniciando vetorização."
        )

        await data_sync_service.load_data_to_vector_db(db, tenant_id)
        logger.info(f"Vetorização para o tenant {tenant_id} concluída com sucesso.")

    except ValueError as e:
        logger.error(f"Erro de valor ao criar tenant {tenant_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Falha crítica durante a criação ou vetorização do tenant {tenant_id}: {e}",
            exc_info=True,
        )
        if tenant:  # Se o tenant foi criado mas a vetorização falhou
            logger.warning(
                f"Iniciando rollback para o tenant {tenant_id} devido a erro na vetorização."
            )
            try:
                tenant_crud.delete_tenant(db, tenant_id)
                logger.info(f"Rollback do tenant {tenant_id} concluído com sucesso.")
            except Exception as del_e:
                logger.critical(
                    f"FALHA CRÍTICA NO ROLLBACK do tenant {tenant_id}. Erro: {del_e}",
                    exc_info=True,
                )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao processar o cadastro do cliente: {e}",
        )

    return tenant


@router.get(
    "/tenants/",
    response_model=List[schemas.Tenant],
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
def get_all_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        tenants = tenant_crud.get_all_tenants(db, skip=skip, limit=limit)
        logger.info(f"Clientes recuperados do banco de dados: {tenants}")
        return tenants
    except Exception as e:
        logger.error(f"Erro ao buscar clientes no banco de dados: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao buscar informações dos clientes.",
        )


@router.get(
    "/tenants/{tenant_id}",
    response_model=schemas.Tenant,
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
def get_tenant(tenant_id: str, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return tenant


@router.put(
    "/tenants/{tenant_id}",
    response_model=schemas.Tenant,
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
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
    db: Session = Depends(get_db),
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

    updated_tenant = tenant_crud.update_tenant(
        db, tenant_id, tenant_update_schema_obj, conteudo_loja
    )

    # Re-carregar dados no PGVector após atualização
    await data_sync_service.load_data_to_vector_db(db, tenant_id)

    return updated_tenant


@router.put(
    "/tenants/{tenant_id}/toggle-status", dependencies=[Depends(get_current_user)]
)
def toggle_tenant_status(
    tenant_id: str, status_data: dict, db: Session = Depends(get_db)
):
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
        salvarBancoDeDados=salvar_banco_de_dados_url,
    )


@router.post(
    "/tenant-data/",
    response_model=schemas.TenantDataResponse,
    dependencies=[Depends(get_current_user)],
)
def get_tenant_data_by_instancia(
    request: schemas.TenantDataRequest, db: Session = Depends(get_db)
):
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
        salvarBancoDeDados=salvar_banco_de_dados_url,
    )


@router.get(
    "/tenants/{tenant_id}/loja_txt",
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
async def get_loja_txt(tenant_id: str, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant or not tenant.config_ai:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Informações da loja não encontradas.",
        )
    return PlainTextResponse(content=tenant.config_ai, media_type="text/plain")


@router.post(
    "/tenants/{tenant_id}/sync-menu",
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
async def sync_menu_from_platform(tenant_id: str, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant or not tenant.url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado ou URL da plataforma de gestão não configurada.",
        )

    try:
        sync_url = f"{tenant.url}/api/menu/{tenant_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(sync_url)
            response.raise_for_status()
            menu_data = response.json()

        # Limpar e repovoar os dados
        await run_in_threadpool(
            product_crud.replace_all_products_for_tenant,
            db,
            tenant_id,
            menu_data.get("produtos", []),
        )
        await run_in_threadpool(
            opcional_crud.replace_all_opcionais_for_tenant,
            db,
            tenant_id,
            menu_data.get("opcionais", []),
        )
        await run_in_threadpool(
            promocao_crud.replace_all_promocoes_for_tenant,
            db,
            tenant_id,
            menu_data.get("promocoes", []),
        )

        # Re-vetorizar os dados
        await data_sync_service.load_data_to_vector_db(db, tenant_id)

        return {"message": "Sincronização concluída com sucesso!"}

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao conectar com a plataforma de gestão: {exc}",
        )
    except Exception as e:
        logger.error(f"Erro inesperado durante a sincronização: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro inesperado durante a sincronização: {e}",
        )


# --- Rotas para Imagens de Cardápio ---


@router.post(
    "/tenants/{tenant_id}/menu-images/",
    response_model=List[schemas.MenuImage],
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
async def upload_menu_images(
    tenant_id: str, files: List[UploadFile] = File(...), db: Session = Depends(get_db)
):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")

    uploaded_images = []
    for file in files:
        image_url = await supabase_client.upload_image_to_supabase(file)
        menu_image_data = schemas.MenuImageCreate(
            image_url=image_url, description=file.filename
        )
        db_menu_image = menu_image_crud.create_menu_image(
            db, menu_image_data, tenant_id
        )
        uploaded_images.append(db_menu_image)

    return uploaded_images


@router.get(
    "/tenants/{tenant_id}/menu-images/",
    response_model=List[schemas.MenuImage],
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
def get_menu_images(tenant_id: str, db: Session = Depends(get_db)):
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    return menu_image_crud.get_menu_images_by_tenant(db, tenant_id)


@router.delete(
    "/tenants/{tenant_id}/menu-images/{image_id}",
    tags=["Tenants"],
    dependencies=[Depends(get_current_user)],
)
async def delete_menu_image(
    tenant_id: str, image_id: int, db: Session = Depends(get_db)
):
    db_menu_image = menu_image_crud.get_menu_image_by_id(db, image_id)
    if not db_menu_image or db_menu_image.tenant_id != tenant_id:
        raise HTTPException(
            status_code=404, detail="Imagem não encontrada para este tenant."
        )

    await supabase_client.delete_image_from_supabase(db_menu_image.image_url)
    menu_image_crud.delete_menu_image(db, image_id)
    return {"message": "Imagem deletada com sucesso."}
