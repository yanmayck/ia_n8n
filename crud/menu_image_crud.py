from core.database import SessionLocal
from core import models, schemas
from typing import List, Optional

def create_menu_image(db_session_factory, menu_image: schemas.MenuImageCreate, tenant_id: str):
    db = db_session_factory()
    try:
        db_menu_image = models.MenuImage(**menu_image.dict(), tenant_id=tenant_id)
        db.add(db_menu_image)
        db.commit()
        db.refresh(db_menu_image)
        return db_menu_image
    finally:
        db.close()

def get_menu_images_by_tenant(db_session_factory, tenant_id: str) -> List[models.MenuImage]:
    db = db_session_factory()
    try:
        return db.query(models.MenuImage).filter(models.MenuImage.tenant_id == tenant_id).all()
    finally:
        db.close()

def get_latest_menu_image_by_tenant(db_session_factory, tenant_id: str) -> Optional[models.MenuImage]:
    db = db_session_factory()
    try:
        return db.query(models.MenuImage).filter(models.MenuImage.tenant_id == tenant_id).order_by(models.MenuImage.id.desc()).first()
    finally:
        db.close()

def get_menu_image_by_id(db_session_factory, image_id: int) -> Optional[models.MenuImage]:
    db = db_session_factory()
    try:
        return db.query(models.MenuImage).filter(models.MenuImage.id == image_id).first()
    finally:
        db.close()

def delete_menu_image(db_session_factory, image_id: int):
    db = db_session_factory()
    try:
        db_menu_image = get_menu_image_by_id(db_session_factory, image_id)
        if db_menu_image:
            db.delete(db_menu_image)
            db.commit()
        return db_menu_image
    finally:
        db.close()
