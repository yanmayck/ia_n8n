from sqlalchemy.orm import Session
from core import models, schemas

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
