
from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
import crud
import models
import schemas
import services
from database import SessionLocal, engine
import os

from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Verifica se a chave da API da Gemini está configurada
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("A variável de ambiente GEMINI_API_KEY não está configurada.")

# Cria as tabelas no banco de dados (se não existirem)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API de Chatbot com Equipe de IAs (CrewAI)",
    description="Processa mensagens multimodais (texto, imagem, áudio) usando uma equipe de agentes de IA.",
    version="3.0.0"
)

templates = Jinja2Templates(directory="templates")

# =======================================================================
# Rota para a Interface Visual
# =======================================================================

@app.get("/", tags=["Interface"])
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# =======================================================================
# Evento de Inicialização para Listar Rotas
# =======================================================================

@app.on_event("startup")
def print_application_routes():
    """Imprime todas as rotas disponíveis na inicialização da aplicação."""
    print("="*80)
    print("Rotas da API disponíveis para conexão com o n8n:")
    print("="*80)
    
    # Cabeçalho da tabela
    print(f"{'Método(s)':<15} {'Rota (Endpoint)':<45} {'Nome da Função'}")
    print("-"*80)

    for route in app.routes:
        # Apenas rotas com métodos (exclui montagens estáticas, etc.)
        if hasattr(route, "methods"):
            methods = ", ".join(route.methods)
            path = route.path
            name = route.name
            print(f"{methods:<15} {path:<45} {name}")
    
    print("="*80)

# =======================================================================
# Dependência do Banco de Dados
# =======================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =======================================================================
# Endpoints para Gerenciamento de Clientes (Tenants)
# =======================================================================

@app.post("/tenants/config", response_model=schemas.Tenant, tags=["Tenants"])
def get_tenant_config(request: schemas.TenantConfigRequest, db: Session = Depends(get_db)):
    tenant = crud.get_tenant_by_id(db, tenant_id=request.instancia)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado ou inativo.")
    return tenant

@app.post("/tenants/", response_model=schemas.Tenant, tags=["Tenants"])
def create_tenant(tenant: schemas.TenantCreate, db: Session = Depends(get_db)):
    db_tenant = crud.get_tenant_by_id(db, tenant_id=tenant.tenant_id)
    if db_tenant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cliente com este ID já existe.")
    return crud.create_tenant(db=db, tenant=tenant)

@app.get("/tenants/", response_model=List[schemas.Tenant], tags=["Tenants"])
def get_all_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tenants = crud.get_all_tenants(db, skip=skip, limit=limit)
    return tenants

@app.put("/tenants/{tenant_id}", response_model=schemas.Tenant, tags=["Tenants"])
def update_tenant(tenant_id: str, tenant: schemas.TenantUpdate, db: Session = Depends(get_db)):
    db_tenant = crud.update_tenant(db, tenant_id=tenant_id, tenant=tenant)
    if not db_tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")
    return db_tenant

# =======================================================================
# Endpoint Principal da IA com CrewAI
# =======================================================================

@app.post("/ai", response_model=List[schemas.AIWebhookResponse], tags=["IA"])
def handle_ai_webhook(request: schemas.AIWebhookRequest, db: Session = Depends(get_db)):
    try:
        ai_response = services.process_message_with_crew(
            db=db,
            user_phone=request.user_phone,
            whatsapp_message_id=request.whatsapp_message_id,
            message_text=request.message_user,
            message_base64=request.message_base64,
            mimetype=request.mimetype,
            personality_name=request.personality_name
        )
        return ai_response

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        # Idealmente, logar o erro aqui
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro interno do servidor: {str(e)}")

# =======================================================================
# Endpoint para Gerenciamento de Personalidades da IA
# =======================================================================

@app.post("/personalities/", response_model=schemas.Personality, tags=["Personalities"])
def create_personality(personality: schemas.PersonalityCreate, db: Session = Depends(get_db)):
    db_personality = crud.get_personality_by_name(db, name=personality.name)
    if db_personality:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Personalidade com o nome '{personality.name}' já existe.")
    return crud.create_personality(db=db, personality=personality)

# =======================================================================
# Endpoint para Recuperação de Arquivos
# =======================================================================

@app.get("/get-file/{retrieval_key}", tags=["Files"])
def get_file(retrieval_key: str, db: Session = Depends(get_db)):
    # Em um cenário real, o arquivo seria buscado de um S3, Google Drive, etc.
    # e retornado com o content-type correto (e.g., image/png, application/pdf).

    # Simulação: verificar se a chave existe em algum produto
    product = crud.get_product_by_retrieval_key(db, retrieval_key=retrieval_key)

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado com esta chave.")

    # Simulação da resposta
    return {"message": f"Arquivo para a chave '{retrieval_key}' seria entregue aqui.", "product_name": product.name}

@app.post("/upload-products", tags=["Products"])
async def upload_products(tenant_id: str, file: UploadFile, db: Session = Depends(get_db)):
    try:
        products = await services.process_product_sheet(tenant_id, file, db)
        return {"message": f"{len(products)} products uploaded successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/products/{tenant_id}", response_model=List[schemas.Product], tags=["Products"])
def get_products(tenant_id: str, db: Session = Depends(get_db)):
    return crud.get_products_by_tenant_id(db, tenant_id=tenant_id)
