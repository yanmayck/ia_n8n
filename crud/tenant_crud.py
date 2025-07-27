from sqlalchemy.orm import Session
from core import models, schemas
from typing import Optional

def get_tenant_by_id(db: Session, tenant_id: str):
    return db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()

def create_tenant(db: Session, tenant: schemas.TenantCreate, conteudo_loja: str):
    from .personality_crud import create_personality, get_personality_by_name

    db_personality = get_personality_by_name(db, name=tenant.ia_personality)
    if db_personality:
        db_personality.prompt = tenant.ai_prompt_description
    else:
        new_personality_data = schemas.PersonalityCreate(
            name=tenant.ia_personality,
            prompt=tenant.ai_prompt_description
        )
        db_personality = create_personality(db, new_personality_data)

    db_tenant = models.Tenant(
        tenant_id=tenant.tenant_id,
        nome_loja=tenant.nome_loja,
        config_ai=conteudo_loja,
        evolution_api_key=None,
        is_active=True,
        personality=db_personality,
        endereco=tenant.endereco,
        cep=tenant.cep,
        latitude=str(tenant.latitude),
        longitude=str(tenant.longitude),
        url=tenant.url,
        freight_config=tenant.freight_config
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def create_tenant_instancia(db: Session, tenant_data: schemas.TenantInstancia):
    from .personality_crud import create_personality, get_personality_by_name

    # Procura ou cria a personalidade
    db_personality = get_personality_by_name(db, name=tenant_data.id_pronpt)
    if not db_personality:
        new_personality_data = schemas.PersonalityCreate(
            name=tenant_data.id_pronpt,
            prompt=f"Prompt padrão para {tenant_data.id_pronpt}" # Adiciona um prompt padrão
        )
        db_personality = create_personality(db, new_personality_data)

    db_tenant = models.Tenant(
        tenant_id=tenant_data.instancia,
        nome_loja=tenant_data.instancia,
        config_ai="",
        evolution_api_key=None,
        is_active=tenant_data.is_active,
        personality=db_personality, # Associa o objeto de personalidade
        url=tenant_data.url
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def get_all_tenants(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Tenant).offset(skip).limit(limit).all()

def update_tenant(db: Session, tenant_id: str, tenant_data: schemas.TenantUpdateSchema, conteudo_loja: Optional[str] = None):
    from .personality_crud import create_personality, get_personality_by_name, update_personality

    db_tenant = db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()
    if not db_tenant:
        return None
    
    update_data = tenant_data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        if hasattr(db_tenant, key) and key not in ["ia_personality", "ai_prompt_description"]:
            setattr(db_tenant, key, value)

    if conteudo_loja is not None:
        db_tenant.config_ai = conteudo_loja

    if "ia_personality" in update_data:
        personality_name = update_data["ia_personality"]
        ai_prompt_description = update_data.get("ai_prompt_description", "")

        db_personality = get_personality_by_name(db, name=personality_name)

        if db_personality:
            if ai_prompt_description:
                personality_update_data = schemas.PersonalityCreate(name=personality_name, prompt=ai_prompt_description)
                update_personality(db, db_personality, personality_update_data)
        else:
            new_personality_data = schemas.PersonalityCreate(
                name=personality_name,
                prompt=ai_prompt_description
            )
            db_personality = create_personality(db, new_personality_data)
        
        db_tenant.personality = db_personality

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

def get_tenant_by_user_phone(db: Session, user_phone: str):
    interaction = db.query(models.Interaction).filter(models.Interaction.user_phone == user_phone).first()
    if interaction and interaction.personality_id:
        personality = db.query(models.Personality).filter(models.Personality.id == interaction.personality_id).first()
        if personality:
            # Corrigido para buscar pelo ID da personalidade, não pelo nome
            return db.query(models.Tenant).filter(models.Tenant.personality_id == personality.id).first()
    return None