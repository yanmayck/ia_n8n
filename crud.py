
from sqlalchemy.orm import Session
import models
import schemas

# =======================================================================
# Funções CRUD para Tenants (Clientes)
# =======================================================================

def get_tenant_by_id(db: Session, tenant_id: str):
    return db.query(models.Tenant).filter(models.Tenant.tenant_id == tenant_id).first()

def create_tenant(db: Session, tenant: schemas.TenantCreate):
    db_tenant = models.Tenant(**tenant.dict())
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant

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
