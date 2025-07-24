import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from crud import personality_crud
from core import schemas
from api.dependencies import get_db, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/personalities/", response_model=schemas.Personality, tags=["Personalities"], dependencies=[Depends(get_current_user)])
def create_personality(personality: schemas.PersonalityCreate, db: Session = Depends(get_db)):
    logger.info(f"Tentando criar personalidade: {personality.name}")
    db_personality = personality_crud.get_personality_by_name(db, name=personality.name)
    if db_personality:
        logger.warning(f"Tentativa de criar personalidade existente: {personality.name}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Personalidade com o nome '{personality.name}' já existe.")
    new_personality = personality_crud.create_personality(db=db, personality=personality)
    logger.info(f"Personalidade {personality.name} criada com sucesso.")
    return new_personality

@router.get("/personalities/", response_model=List[schemas.Personality], tags=["Personalities"], dependencies=[Depends(get_current_user)])
def get_all_personalities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retorna todas as personalidades da IA."""
    personalities = personality_crud.get_all_personalities(db, skip=skip, limit=limit)
    return personalities

@router.get("/personalities/{personality_name}", response_model=schemas.Personality, tags=["Personalities"], dependencies=[Depends(get_current_user)])
def get_personality_by_name(personality_name: str, db: Session = Depends(get_db)):
    """Retorna uma personalidade da IA pelo nome."""
    personality = personality_crud.get_personality_by_name(db, name=personality_name)
    if personality is None:
        raise HTTPException(status_code=404, detail="Personalidade não encontrada")
    return personality

@router.put("/personalities/{personality_name}", response_model=schemas.Personality, tags=["Personalities"], dependencies=[Depends(get_current_user)])
def update_personality(personality_name: str, personality: schemas.PersonalityCreate, db: Session = Depends(get_db)):
    """Atualiza uma personalidade da IA existente."""
    db_personality = personality_crud.get_personality_by_name(db, name=personality_name)
    if db_personality is None:
        raise HTTPException(status_code=404, detail="Personalidade não encontrada")
    
    if personality.name != personality_name and personality_crud.get_personality_by_name(db, name=personality.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Já existe uma personalidade com o nome '{personality.name}'.")

    updated_personality = personality_crud.update_personality(db, db_personality, personality)
    return updated_personality

@router.delete("/personalities/{personality_name}", tags=["Personalities"], dependencies=[Depends(get_current_user)])
def delete_personality(personality_name: str, db: Session = Depends(get_db)):
    """Deleta uma personalidade da IA."""
    personality = personality_crud.get_personality_by_name(db, name=personality_name)
    if personality is None:
        raise HTTPException(status_code=404, detail="Personalidade não encontrada")
    personality_crud.delete_personality(db, personality)
    return {"message": "Personalidade deletada com sucesso."}
