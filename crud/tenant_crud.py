from sqlalchemy.orm import Session
from core import models, schemas
from typing import Optional

def get_tenant_by_id(db: Session, tenant_id: str):
    return db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()

def create_tenant(db: Session, tenant: schemas.TenantCreate, conteudo_loja: str, menu_image_url: Optional[str] = None):
    from .personality_crud import create_personality, get_personality_by_name # Importação local

    db_personality = get_personality_by_name(db, name=tenant.ia_personality)
    if db_personality:
        db_personality.prompt = tenant.ai_prompt_description
    else:
        new_personality_data = schemas.PersonalityCreate(
            name=tenant.ia_personality,
            prompt=tenant.ai_prompt_description,
            tenant_id=tenant.tenant_id
        )
        db_personality = create_personality(db, new_personality_data)

    db_tenant = models.Tenant(
        tenant_id=tenant.tenant_id,
        nome_loja=tenant.nome_loja,
        config_ai=conteudo_loja,
        evolution_api_key=None,
        is_active=True,
        id_pronpt=tenant.ia_personality,
        endereco=tenant.endereco,
        cep=tenant.cep,
        latitude=str(tenant.latitude),
        longitude=str(tenant.longitude),
        url=tenant.url,
        menu_image_url=menu_image_url,
        freight_config=tenant.freight_config # Adicionando o novo campo
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def create_tenant_instancia(db: Session, tenant_data: schemas.TenantInstancia):
    db_tenant = models.Tenant(
        tenant_id=tenant_data.instancia,
        nome_loja=tenant_data.instancia,
        config_ai="",
        evolution_api_key=None,
        is_active=tenant_data.is_active,
        id_pronpt=tenant_data.id_pronpt,
        url=tenant_data.url
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def get_all_tenants(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Tenant).offset(skip).limit(limit).all()

def update_tenant(db: Session, tenant_id: str, tenant_data: schemas.TenantUpdateSchema, conteudo_loja: Optional[str] = None, menu_image_url: Optional[str] = None):
    from .personality_crud import create_personality, get_personality_by_name # Importação local

    db_tenant = db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()
    if not db_tenant:
        return None
    
    update_data = tenant_data.model_dump(exclude_unset=True)
    
    if "nome_loja" in update_data: db_tenant.nome_loja = update_data["nome_loja"]
    if "endereco" in update_data: db_tenant.endereco = update_data["endereco"]
    if "cep" in update_data: db_tenant.cep = update_data["cep"]
    if "latitude" in update_data: db_tenant.latitude = str(update_data["latitude"])
    if "longitude" in update_data: db_tenant.longitude = str(update_data["longitude"])
    if "url" in update_data: db_tenant.url = update_data["url"]
    if "is_active" in update_data: db_tenant.is_active = update_data["is_active"]
    if "freight_config" in update_data: db_tenant.freight_config = update_data["freight_config"] # Adicionando o novo campo
    if menu_image_url is not None:
        db_tenant.menu_image_url = menu_image_url

    if conteudo_loja is not None: 
        db_tenant.config_ai = conteudo_loja
    
    if "ia_personality" in update_data and update_data["ia_personality"] is not None:
        personality_name = update_data["ia_personality"]
        ai_prompt_description = update_data.get("ai_prompt_description")

        db_personality = get_personality_by_name(db, name=personality_name)
        if db_personality:
            if ai_prompt_description is not None:
                db_personality.prompt = ai_prompt_description
        else:
            if ai_prompt_description is not None:
                new_personality_data = schemas.PersonalityCreate(
                    name=personality_name,
                    prompt=ai_prompt_description,
                    tenant_id=tenant_id
                )
                create_personality(db, new_personality_data)

        if personality_name is not None:
            db_tenant.id_pronpt = personality_name
    
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def toggle_tenant_status(db: Session, tenant_id: str, is_active: bool):
    db_tenant = db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()
    if not db_tenant:
        return None
    
    db_tenant.is_active = is_active
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def delete_tenant(db: Session, tenant_id: str):
    db_tenant = db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()
    if not db_tenant:
        return None
    
    db.delete(db_tenant)
    db.commit()
    return {"message": "Cliente removido com sucesso"}

def get_tenant_by_personality_name(db: Session, personality_name: str):
    return db.query(models.Tenant).filter(models.Tenant.id_pronpt == personality_name).first()

def get_tenant_by_user_phone(db: Session, user_phone: str):
    interaction = db.query(models.Interaction).filter(models.Interaction.user_phone == user_phone).first()
    if interaction and interaction.personality_id:
        personality = db.query(models.Personality).filter(models.Personality.id == interaction.personality_id).first()
        if personality:
            return db.query(models.Tenant).filter(models.Tenant.id_pronpt == personality.name).first()
    return None
