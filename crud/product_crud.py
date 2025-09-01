import logging
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from core import models, schemas
from typing import List

logger = logging.getLogger(__name__)

def get_product(db: Session, product_id: int):
    return (
        db.query(models.Product)
        .options(joinedload(models.Product.opcionais), joinedload(models.Product.promocoes))
        .filter(models.Product.id_produto == product_id)
        .first()
    )

def get_product_by_name_and_tenant(db: Session, name: str, tenant_id: str) -> models.Product | None:
    """
    Busca um produto específico pelo nome ou descrição e pelo ID do tenant.
    A busca é case-insensitive e procura por substrings.
    """
    return db.query(models.Product).filter(
        or_(
            models.Product.nome_produto.ilike(f"%{name}%"),
            models.Product.descricao_produto.ilike(f"%{name}%")
        ),
        models.Product.tenant_id == tenant_id
    ).first()

def get_products_by_tenant(db: Session, tenant_id: str, skip: int = 0, limit: int = 100):
    return db.query(models.Product).filter(models.Product.tenant_id == tenant_id).offset(skip).limit(limit).all()

def get_all_products_with_details(db: Session, tenant_id: str):
    """
    Busca todos os produtos de um tenant, carregando seus opcionais e promoções
    de forma otimizada para evitar múltiplas queries (problema N+1).
    """
    return (
        db.query(models.Product)
        .filter(models.Product.tenant_id == tenant_id)
        .options(
            joinedload(models.Product.opcionais),
            joinedload(models.Product.promocoes)
        )
        .all()
    )

def create_product(db: Session, product: schemas.ProductCreate, tenant_id: str):
    logger.info(f"CRUD: Criando objeto Product no modelo para o tenant '{tenant_id}'.")
    db_product = models.Product(**product.model_dump(), tenant_id=tenant_id)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    logger.info(f"CRUD: Produto '{db_product.nome_produto}' (ID: {db_product.id_produto}) comitado no banco de dados.")
    return db_product

def update_product(db: Session, product_id: int, product_data: schemas.ProductUpdate):
    db_product = get_product(db, product_id)
    if db_product:
        update_data = product_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
    return db_product

def delete_product(db: Session, product_id: int):
    db_product = get_product(db, product_id)
    if db_product:
        db.delete(db_product)
        db.commit()
    return db_product

def link_opcional_to_product(db: Session, product_id: int, opcional_id: int):
    product = db.query(models.Product).filter(models.Product.id_produto == product_id).first()
    opcional = db.query(models.Opcional).filter(models.Opcional.id_opcional == opcional_id).first()
    if product and opcional:
        product.opcionais.append(opcional)
        db.commit()
        return product
    return None

def unlink_opcional_from_product(db: Session, product_id: int, opcional_id: int):
    product = db.query(models.Product).filter(models.Product.id_produto == product_id).first()
    opcional = db.query(models.Opcional).filter(models.Opcional.id_opcional == opcional_id).first()
    if product and opcional:
        try:
            product.opcionais.remove(opcional)
            db.commit()
            return product
        except ValueError:
            pass # Opcional not in product.opcionais
    return None

def get_linked_opcionais(db: Session, product_id: int) -> List[models.Opcional]:
    product = db.query(models.Product).options(joinedload(models.Product.opcionais)).filter(models.Product.id_produto == product_id).first()
    if product:
        return product.opcionais
    return []

def link_promocao_to_product(db: Session, product_id: int, promocao_id: int):
    product = db.query(models.Product).filter(models.Product.id_produto == product_id).first()
    promocao = db.query(models.Promocao).filter(models.Promocao.id_promocao == promocao_id).first()
    if product and promocao:
        product.promocoes.append(promocao)
        db.commit()
        return product
    return None

def unlink_promocao_from_product(db: Session, product_id: int, promocao_id: int):
    product = db.query(models.Product).filter(models.Product.id_produto == product_id).first()
    promocao = db.query(models.Promocao).filter(models.Promocao.id_promocao == promocao_id).first()
    if product and promocao:
        try:
            product.promocoes.remove(promocao)
            db.commit()
            return product
        except ValueError:
            pass
    return None

def get_linked_promocoes(db: Session, product_id: int) -> List[models.Promocao]:
    product = db.query(models.Product).options(joinedload(models.Product.promocoes)).filter(models.Product.id_produto == product_id).first()
    if product:
        return product.promocoes
    return []

def get_product_by_name_and_tenant(db: Session, name: str, tenant_id: str) -> models.Product | None:
    """
    Busca um produto específico pelo nome ou descrição e pelo ID do tenant.
    A busca é case-insensitive e procura por substrings.
    """
    return db.query(models.Product).filter(
        or_(
            models.Product.nome_produto.ilike(f"%{name}%"),
            models.Product.descricao_produto.ilike(f"%{name}%")
        ),
        models.Product.tenant_id == tenant_id
    ).first()

def replace_all_products_for_tenant(db: Session, tenant_id: str, products_data: List[schemas.ProductCreate]):
    """
    Deleta todos os produtos existentes de um tenant e insere os novos.
    """
    db.query(models.Product).filter(models.Product.tenant_id == tenant_id).delete(synchronize_session=False)
    
    new_products = []
    for prod_data in products_data:
        new_prod = models.Product(
            tenant_id=tenant_id,
            nome_produto=prod_data.nome_produto,
            descricao_produto=prod_data.descricao_produto,
            categoria_produto=prod_data.categoria_produto,
            preco_base=prod_data.preco_base,
            tempo_preparo_min=prod_data.tempo_preparo_min,
            disponivel_hoje=prod_data.disponivel_hoje
        )
        new_products.append(new_prod)
        
    if new_products:
        db.bulk_save_objects(new_products)
    
    db.commit()
