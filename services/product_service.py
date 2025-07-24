import pandas as pd
import io
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from core import models, schemas
from crud import product_crud
from fastapi import UploadFile

async def process_product_sheet(tenant_id: str, file: UploadFile, db: Session):
    products_content = await file.read()
    df = await run_in_threadpool(pd.read_excel, io.BytesIO(products_content))
    df.columns = df.columns.str.strip()

    saved_products = []
    for _, row in df.iterrows():
        produto = models.Product(
            name=row['Plano_(Produto)'],
            price=str(row['Preço_Sugerido_(Mensal)']),
            retrieval_key=row.get('retrieval_key', f"{tenant_id}_{row['Plano_(Produto)']}"),
            tenant_id=tenant_id,
            publico_alvo=row.get('Público-Alvo'),
            principais_funcionalidades=row.get('Principais_Funcionalidades'),
            limitacoes_observacoes=row.get('Limitações/Observações'),
            produto_promocao=row.get('produto_promocao'),
            preco_promotions=row.get('preco_promotions'),
            combo_product=row.get('combo_product'),
            tempo_preparo_minutos=row.get('tempo_preparo_minutos')
        )
        db.add(produto)
        saved_products.append(produto)
    db.commit()
    return saved_products
