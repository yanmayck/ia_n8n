from sqlalchemy.orm import Session
from core import models, schemas
from sqlalchemy.sql import func

def get_user_address(db: Session, user_phone: str, tenant_id: str):
    return (
        db.query(models.UserAddress)
        .filter(
            models.UserAddress.user_phone == user_phone,
            models.UserAddress.tenant_id == tenant_id
        )
        .order_by(models.UserAddress.last_used_at.desc())
        .first()
    )

def create_or_update_user_address(db: Session, address: schemas.UserAddressCreate):
    db_address = get_user_address(db, user_phone=address.user_phone, tenant_id=address.tenant_id)
    if db_address:
        db_address.address_text = address.address_text
        db_address.latitude = address.latitude
        db_address.longitude = address.longitude
        db_address.last_used_at = func.now()
    else:
        db_address = models.UserAddress(**address.dict())
        db.add(db_address)
    db.commit()
    db.refresh(db_address)
    return db_address
