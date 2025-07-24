from sqlalchemy.orm import Session
from core import models, schemas

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
