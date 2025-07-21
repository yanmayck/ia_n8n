
from sqlalchemy.orm import Session
from core import models
from core import schemas
from typing import Optional

# =======================================================================
# Funções CRUD para Tenants (Clientes)
# =======================================================================

def get_tenant_by_id(db: Session, tenant_id: str):
    return db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()

def create_tenant(db: Session, tenant: schemas.TenantCreate, conteudo_loja: str, menu_image_url: Optional[str] = None):
    # Criar ou atualizar a personalidade da IA
    db_personality = get_personality_by_name(db, name=tenant.ia_personality)
    if db_personality:
        # Atualizar prompt se já existe
        db_personality.prompt = tenant.ai_prompt_description
    else:
        # Criar nova personalidade
        new_personality_data = schemas.PersonalityCreate(
            name=tenant.ia_personality,
            prompt=tenant.ai_prompt_description,
            tenant_id=tenant.tenant_id # Associar a personalidade ao tenant
        )
        db_personality = create_personality(db, new_personality_data)

    db_tenant = models.Tenant(
        tenant_id=tenant.tenant_id,
        nome_loja=tenant.nome_loja,
        config_ai=conteudo_loja,  # Salva o conteúdo do txt
        evolution_api_key=None,
        is_active=True,
        id_pronpt=tenant.ia_personality, # Garante que o tenant_id da personalidade seja o nome da personalidade
        endereco=tenant.endereco,
        cep=tenant.cep,
        latitude=str(tenant.latitude),
        longitude=str(tenant.longitude),
        url=tenant.url,
        menu_image_url=menu_image_url # Adicionar a URL da imagem do cardápio aqui
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

def create_tenant_instancia(db: Session, tenant_data: schemas.TenantInstancia):
    """Criar tenant via JSON com chave 'instancia'"""
    db_tenant = models.Tenant(
        tenant_id=tenant_data.instancia,
        nome_loja=tenant_data.instancia,  # Usar instância como nome da loja
        config_ai="",  # Vazio inicialmente
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
    db_tenant = db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()
    if not db_tenant:
        return None
    
    # Atualizar campos do tenant se fornecidos
    update_data = tenant_data.model_dump(exclude_unset=True)
    
    if "nome_loja" in update_data: db_tenant.nome_loja = update_data["nome_loja"]
    if "endereco" in update_data: db_tenant.endereco = update_data["endereco"]
    if "cep" in update_data: db_tenant.cep = update_data["cep"]
    if "latitude" in update_data: db_tenant.latitude = str(update_data["latitude"])
    if "longitude" in update_data: db_tenant.longitude = str(update_data["longitude"])
    if "url" in update_data: db_tenant.url = update_data["url"]
    if "is_active" in update_data: db_tenant.is_active = update_data["is_active"]
    if menu_image_url is not None: # Atualizar menu_image_url se um novo foi fornecido
        db_tenant.menu_image_url = menu_image_url

    # Atualizar config_ai se um novo arquivo loja_txt foi enviado
    if conteudo_loja is not None: 
        db_tenant.config_ai = conteudo_loja
    
    # Lidar com a personalidade da IA
    # Check if ia_personality is provided and is a valid string
    if "ia_personality" in update_data and update_data["ia_personality"] is not None:
        personality_name = update_data["ia_personality"]
        ai_prompt_description = update_data.get("ai_prompt_description") # Get with default None if not present

        db_personality = get_personality_by_name(db, name=personality_name)
        if db_personality:
            # If personality exists, update its prompt only if a new prompt is provided and not None
            if ai_prompt_description is not None:
                db_personality.prompt = ai_prompt_description
        else:
            # If personality does not exist, create it only if a valid prompt is also provided
            if ai_prompt_description is not None:
                new_personality_data = schemas.PersonalityCreate(
                    name=personality_name,
                    prompt=ai_prompt_description,
                    tenant_id=tenant_id
                )
                create_personality(db, new_personality_data)

        # Update the tenant's personality reference only if personality_name is not None
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
    """Busca um tenant pelo nome da personalidade (id_pronpt)."""
    return db.query(models.Tenant).filter(models.Tenant.id_pronpt == personality_name).first()


def get_tenant_by_user_phone(db: Session, user_phone: str):
    """Busca o primeiro tenant associado a uma interação de um determinado número de telefone."""
    # Esta é uma implementação de exemplo. A lógica exata pode precisar ser ajustada
    # dependendo de como um 'user_phone' se relaciona com um 'tenant'.
    # Aqui, estamos assumindo que podemos encontrar o tenant através das interações.
    interaction = db.query(models.Interaction).filter(models.Interaction.user_phone == user_phone).first()
    if interaction and interaction.personality_id:
        personality = db.query(models.Personality).filter(models.Personality.id == interaction.personality_id).first()
        if personality:
            return db.query(models.Tenant).filter(models.Tenant.id_pronpt == personality.name).first()
    return None


def get_interaction_by_whatsapp_id(db: Session, whatsapp_message_id: str):
    """Busca uma interação pelo seu whatsapp_message_id para verificar duplicidade."""
    return db.query(models.Interaction).filter(models.Interaction.whatsapp_message_id == whatsapp_message_id).first()

# =======================================================================
# Funções CRUD para Personalities (IA)
# =======================================================================

def get_personality_by_name(db: Session, name: str):
    return db.query(models.Personality).filter(models.Personality.name == name).first()

def create_personality(db: Session, personality: schemas.PersonalityCreate):
    db_personality = models.Personality(name=personality.name, prompt=personality.prompt)
    db.add(db_personality)
    db.commit()
    db.refresh(db_personality)
    return db_personality

def get_all_personalities(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Personality).offset(skip).limit(limit).all()

def update_personality(db: Session, db_personality: models.Personality, personality: schemas.PersonalityCreate):
    db_personality.name = personality.name
    db_personality.prompt = personality.prompt
    db.commit()
    db.refresh(db_personality)
    return db_personality

def delete_personality(db: Session, personality: models.Personality):
    db.delete(personality)
    db.commit()
    return {"message": "Personalidade deletada com sucesso"}

# =======================================================================
# Funções CRUD para Interactions (Histórico)
# =======================================================================

def create_interaction(db: Session, interaction: schemas.InteractionCreate):
    db_interaction = models.Interaction(**interaction.dict())
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    return db_interaction

def get_interactions_by_user_phone(db: Session, user_phone: str, limit: int = 10):
    """Busca as últimas 'limit' interações para um usuário, ordenadas da mais antiga para a mais recente."""
    return db.query(models.Interaction)\
        .filter(models.Interaction.user_phone == user_phone)\
        .order_by(models.Interaction.created_at.desc())\
        .limit(limit)\
        .all()[::-1] # Inverte a lista para ter a ordem cronológica correta (mais antiga primeiro)


# =======================================================================
# Funções CRUD para Products
# =======================================================================

def get_product_by_retrieval_key(db: Session, retrieval_key: str):
    return db.query(models.Product).filter(models.Product.retrieval_key == retrieval_key).first()

def get_products_by_tenant_id(db: Session, tenant_id: str):
    return db.query(models.Product).filter(models.Product.tenant_id == tenant_id).all()

def create_product(db: Session, product: schemas.ProductCreate):
    db_product = models.Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def get_product_by_name_and_tenant_id(db: Session, name: str, tenant_id: str):
    return db.query(models.Product).filter(
        models.Product.name == name,
        models.Product.tenant_id == tenant_id
    ).first()

def update_product(db: Session, existing_product: models.Product, product_data: schemas.ProductCreate):
    for field, value in product_data.dict(exclude_unset=True).items():
        setattr(existing_product, field, value)
    db.add(existing_product)
    db.commit()
    db.refresh(existing_product)
    return existing_product

def delete_product(db: Session, product_id: int):
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if db_product:
        db.delete(db_product)
        db.commit()
        return True
    return False

def get_product_by_id(db: Session, product_id: int):
    return db.query(models.Product).filter(models.Product.id == product_id).first()
