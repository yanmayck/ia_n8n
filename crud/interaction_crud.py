from sqlalchemy.orm import Session
from core import models, schemas

def create_interaction(db: Session, interaction: schemas.InteractionCreate):
    db_interaction = models.Interaction(**interaction.dict())
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    return db_interaction

def get_interactions_by_user_phone(db: Session, user_phone: str, limit: int = 10):
    """Busca as últimas 'limit' interações para um usuário, ordenadas da mais antiga para a mais recente."""
    return (
        db.query(models.Interaction)
        .filter(models.Interaction.user_phone == user_phone)
        .order_by(models.Interaction.created_at.desc())
        .limit(limit)
        .all()[::-1]
    )

def get_interaction_by_whatsapp_id(db: Session, whatsapp_message_id: str):
    """Busca uma interação pelo seu whatsapp_message_id para verificar duplicidade."""
    return db.query(models.Interaction).filter(models.Interaction.whatsapp_message_id == whatsapp_message_id).first()

