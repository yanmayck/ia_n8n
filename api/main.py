import logging
from logging.config import dictConfig
import os
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

from core.logging_config import LOGGING_CONFIG
from core import models
from core.database import engine
from api.routers import tenants, ai, personalities, products, authentication

# Configuração de Logging
dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

# Validação das variáveis de ambiente
if not os.getenv("SECRET_KEY"):
    raise ValueError("A variável de ambiente SECRET_KEY não está configurada para JWT.")
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("A variável de ambiente GEMINI_API_KEY não está configurada.")

# Cria as tabelas no banco de dados
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API de Chatbot com Equipe de IAs (Agno)",
    description="Processa mensagens multimodais usando uma equipe de agentes de IA.",
    version="4.0.0"
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="templates"), name="static")

# --- Rota da Interface e Inclusão dos Roteadores ---

@app.get("/", tags=["Interface"])
async def read_root(request: Request):
    logger.info("Requisição recebida para a rota raiz.")
    return templates.TemplateResponse("index.html", {"request": request})

# Incluir os roteadores da API
app.include_router(authentication.router)
app.include_router(tenants.router)
app.include_router(ai.router)
app.include_router(personalities.router)
app.include_router(products.router)

@app.on_event("startup")
def print_application_routes():
    """Imprime todas as rotas disponíveis na inicialização da aplicação."""
    print("="*80)
    print("Rotas da API disponíveis:")
    print("="*80)
    print(f"{'Método(s)':<15} {'Rota (Endpoint)':<45} {'Nome da Função'}")
    print("-"*80)
    for route in app.routes:
        if hasattr(route, "methods"):
            print(f"{', '.join(route.methods):<15} {route.path:<45} {route.name}")
    print("="*80)
