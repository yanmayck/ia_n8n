from core.database import SessionLocalLocal
from core import models, schemas

def create_order(db_session_factory, order: schemas.OrderCreate):
    db = db_session_factory()
    try:
        db_order = models.Order(**order.dict())
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        return db_order
    finally:
        db.close()
