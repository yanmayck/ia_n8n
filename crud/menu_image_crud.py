from sqlalchemy.orm import Session
from core import models, schemas
from typing import List, Optional

def create_menu_image(db: Session, menu_image: schemas.MenuImageCreate, tenant_id: str):
    db_menu_image = models.MenuImage(**menu_image.model_dump(), tenant_id=tenant_id)
    db.add(db_menu_image)
    db.commit()
    db.refresh(db_menu_image)
    return db_menu_image

def get_menu_images_by_tenant(db: Session, tenant_id: str) -> List[models.MenuImage]:
    return db.query(models.MenuImage).filter(models.MenuImage.tenant_id == tenant_id).all()

def get_latest_menu_image_by_tenant(db: Session, tenant_id: str) -> Optional[models.MenuImage]:
    return db.query(models.MenuImage).filter(models.MenuImage.tenant_id == tenant_id).order_by(models.MenuImage.id.desc()).first()

def get_menu_image_by_id(db: Session, image_id: int) -> Optional[models.MenuImage]:
    return db.query(models.MenuImage).filter(models.MenuImage.id == image_id).first()

def delete_menu_image(db: Session, image_id: int):
    db_menu_image = get_menu_image_by_id(db, image_id)
    if db_menu_image:
        db.delete(db_menu_image)
        db.commit()
    return db_menu_image

def replace_all_images_for_tenant(db: Session, tenant_id: str, images_data: List[schemas.MenuImageCreate]):
    """
    Deleta todas as imagens de menu existentes de um tenant e insere as novas.
    """
    db.query(models.MenuImage).filter(models.MenuImage.tenant_id == tenant_id).delete(synchronize_session=False)
    
    new_images = []
    for img_data in images_data:
        new_img = models.MenuImage(**img_data.model_dump(), tenant_id=tenant_id)
        new_images.append(new_img)
        
    if new_images:
        db.bulk_save_objects(new_images)
    
    db.commit()
