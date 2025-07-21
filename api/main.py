import logging
import os
from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles # Importar StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional # Importado para JWT
from jose import JWTError, jwt # Importado para JWT
from datetime import datetime, timedelta # Importado para JWT

from crud import crud # Importa o módulo crud da pasta crud
from core import models # Importa o módulo models da pasta core
from core import schemas # Importa o módulo schemas da pasta core
from services import services # Importa o módulo services da pasta services
from core.database import SessionLocal, engine # Importa SessionLocal e engine da pasta core/database
import pandas as pd
import io # Adicionado para usar io.BytesIO
from openpyxl import Workbook
from fastapi.responses import StreamingResponse

from dotenv import load_dotenv
import uuid # Para gerar nomes de arquivo únicos
import mimetypes # Para determinar o tipo MIME do arquivo
import httpx # Substitui requests para requisições assíncronas
import base64 # Adicionar para codificar imagens em base64

from fastapi.responses import PlainTextResponse # Importar PlainTextResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool # Adicionar este import

# Configuração de Logging
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO, # Nível de log (INFO, DEBUG, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # Saída para o console também
    ]
)

logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações de Autenticação JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Token expira em 30 minutos

# Adicionando log para depuração da SECRET_KEY
logger.info(f"SECRET_KEY carregada: {SECRET_KEY[:4]}...{SECRET_KEY[-4:] if SECRET_KEY and len(SECRET_KEY) > 8 else ''}")

if not SECRET_KEY:
    raise ValueError("A variável de ambiente SECRET_KEY não está configurada para JWT.")

# Verifica se a chave da API da Gemini está configurada
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("A variável de ambiente GEMINI_API_KEY não está configurada.")

# Variáveis de ambiente para APIs
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Variáveis de ambiente Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")

# Funções Auxiliares JWT
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def get_current_user(request: Request):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = request.headers.get("Authorization")

    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
        payload = decode_access_token(token)
        if payload is None:
            raise credentials_exception
        return payload
    raise credentials_exception

# Cria as tabelas no banco de dados (se não existirem)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API de Chatbot com Equipe de IAs (CrewAI)",
    description="Processa mensagens multimodais (texto, imagem, áudio) usando uma equipe de agentes de IA.",
    version="3.0.0"
)

templates = Jinja2Templates(directory="templates")

# Montar arquivos estáticos (CSS, JS) da pasta 'templates'
app.mount("/static", StaticFiles(directory="templates"), name="static")

# REMOVENDO BLOCO TEMPORÁRIO QUE CAUSAVA ERROS DE DEPENDÊNCIA AO DROPAR TABELAS.
# O `models.Base.metadata.create_all(bind=engine)` no início do arquivo ainda
# garante que as tabelas sejam criadas se não existirem.
# @app.on_event("startup")
# def startup_event():
#     logger.info("Aplicação iniciada.")
#     logger.warning("Dropping all tables and recreating (TEMPORARY DEV ACTION).")
#     try:
#         models.Base.metadata.drop_all(bind=engine)
#         logger.info("Todas as tabelas dropadas com sucesso.")
#     except Exception as e:
#         logger.warning(f"Não foi possível dropar todas as tabelas: {e}")
#     models.Base.metadata.create_all(bind=engine);
#     logger.info("Todas as tabelas foram recriadas/verificadas com as últimas definições.")
# =======================================================================

# =======================================================================
# Rota para a Interface Visual
# =======================================================================

@app.get("/", tags=["Interface"])
async def read_root(request: Request):
    logger.info("Requisição recebida para a rota raiz.")
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login")
def login(password: str = Form(...)):
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        logger.error("ADMIN_PASSWORD não configurada no ambiente.")
        raise HTTPException(status_code=500, detail="Senha de administrador não configurada.")

    if password == admin_password:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": "admin"}, expires_delta=access_token_expires
        )
        logger.info("Login de administrador bem-sucedido. Token gerado.")
        return {"message": "Login bem-sucedido", "access_token": access_token, "token_type": "bearer"}
    else:
        logger.warning("Tentativa de login de administrador falhou.")
        raise HTTPException(status_code=401, detail="Senha incorreta.")

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

@app.post("/tenants/config", response_model=schemas.Tenant, tags=["Tenants"], dependencies=[Depends(get_current_user)])
def get_tenant_config(request: schemas.TenantConfigRequest, db: Session = Depends(get_db)):
    tenant = crud.get_tenant_by_id(db, tenant_id=request.instancia)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado ou inativo.")
    return tenant

@app.post("/tenant-instancia/", dependencies=[Depends(get_current_user)])
def create_tenant_instancia(tenant_data: schemas.TenantInstancia, db: Session = Depends(get_db)):
    """Endpoint para receber JSON com chave 'instancia'"""
    return crud.create_tenant_instancia(db, tenant_data)

@app.post("/tenants/", dependencies=[Depends(get_current_user)])
async def create_tenant(
    tenant_id: str = Form(...),  # Instância
    nome_loja: str = Form(...),  # Nome da loja
    ia_personality: str = Form(...),
    ai_prompt_description: str = Form(...), # Novo campo para a descrição do prompt
    endereco: str = Form(...),
    cep: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    loja_txt: UploadFile = File(...),  # Descrição da empresa
    produtos_excel: UploadFile = File(...),  # Tabela de produtos
    menu_image: UploadFile = File(None), # Novo campo para a imagem do cardápio
    db: Session = Depends(get_db)
):
    # Ler arquivo de descrição da empresa
    conteudo_loja = await loja_txt.read()
    conteudo_loja = conteudo_loja.decode("utf-8")
    
    # Processar arquivo Excel de produtos
    produtos_content = await produtos_excel.read()
    
    # Envolver pd.read_excel em run_in_threadpool para assincronicidade e usar io.BytesIO
    df = await run_in_threadpool(pd.read_excel, io.BytesIO(produtos_content))

    # Limpar nomes das colunas (remover espaços em branco)
    df.columns = df.columns.str.strip()

    # =======================================================================
    # ADIÇÃO PARA DEBUG: Imprimir nomes das colunas do Excel
    logger.info(f"Colunas lidas do Excel: {df.columns.tolist()}")
    # =======================================================================
    
    tenant_data = schemas.TenantCreate(
        tenant_id=tenant_id,
        nome_loja=nome_loja,
        ia_personality=ia_personality,
        ai_prompt_description=ai_prompt_description, # Passar a descrição do prompt
        endereco=endereco,
        cep=cep,
        latitude=latitude,
        longitude=longitude
    )
    
    # Upload da imagem do cardápio para o Supabase Storage
    menu_image_url = None
    if menu_image:
        try:
            menu_image_url = await services.upload_image_to_supabase(menu_image)
        except HTTPException as e:
            raise e # Re-raise HTTPException from service layer
        except Exception as e:
            logger.error(f"Erro ao fazer upload da imagem do cardápio para o Supabase: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Erro interno ao fazer upload da imagem do cardápio.")

    # Criar tenant
    tenant = crud.create_tenant(db, tenant_data, conteudo_loja, menu_image_url)
    
    # Salvar produtos do Excel
    saved_products = []
    for _, row in df.iterrows():
        produto = models.Product(
            name=row['Plano_(Produto)'],
            price=str(row['Preço_Sugerido_(Mensal)']),
            retrieval_key=row.get('retrieval_key', f"{tenant_id}_{row['Plano_(Produto)']}"),
            tenant_id=tenant_id,
            publico_alvo=row.get('Público-Alvo'), # Nova coluna
            principais_funcionalidades=row.get('Principais_Funcionalidades'), # Nova coluna
            limitacoes_observacoes=row.get('Limitações/Observações'), # Nova coluna
            produto_promocao=row.get('produto_promocao'), # Nova coluna
            preco_promotions=row.get('preco_promotions'), # Nova coluna
            combo_product=row.get('combo_product') # Nova coluna
        )
        db.add(produto)
        saved_products.append(produto)
    db.commit()

    # A indexação agora é feita "just-in-time" quando o agente é criado.
    # A chamada explícita para 'load_data_to_vector_db' foi REMOVIDA.

    return tenant

@app.get("/tenants/", response_model=List[schemas.Tenant], tags=["Tenants"], dependencies=[Depends(get_current_user)])
def get_all_tenants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tenants = crud.get_all_tenants(db, skip=skip, limit=limit)
    return tenants

@app.get("/tenants/{tenant_id}", response_model=schemas.Tenant, tags=["Tenants"], dependencies=[Depends(get_current_user)])
def get_tenant(tenant_id: str, db: Session = Depends(get_db)):
    tenant = crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return tenant

@app.put("/tenants/{tenant_id}", response_model=schemas.Tenant, tags=["Tenants"], dependencies=[Depends(get_current_user)])
async def update_tenant(
    tenant_id: str,
    # Define explicitamente cada campo do formulário como Optional[type] = Form(None)
    nome_loja: Optional[str] = Form(None),
    ia_personality: Optional[str] = Form(None),
    ai_prompt_description: Optional[str] = Form(None),
    endereco: Optional[str] = Form(None),
    cep: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    url: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None), # FastAPI vai coercer 'true'/'false'/'on'/'' para bool
    
    loja_txt: UploadFile = File(None),
    menu_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Obter o tenant existente para saber a URL da imagem antiga
    existing_tenant = crud.get_tenant_by_id(db, tenant_id)
    if not existing_tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # Construir um dicionário com os dados de atualização,
    # incluindo apenas os campos que foram realmente fornecidos no formulário.
    # Isso evita sobrescrever campos existentes com None se não foram alterados.
    tenant_update_data = {
        "nome_loja": nome_loja,
        "ia_personality": ia_personality,
        "ai_prompt_description": ai_prompt_description,
        "endereco": endereco,
        "cep": cep,
        "latitude": latitude,
        "longitude": longitude,
        "url": url,
        "is_active": is_active,
    }
    # Filtrar valores None, a menos que sejam explicitamente False para booleanos
    # (para o is_active, se for False, queremos que ele seja atualizado)
    filtered_update_data = {}
    for key, value in tenant_update_data.items():
        if value is not None or (key == "is_active" and value is False):
            filtered_update_data[key] = value

    # Criar uma instância de TenantUpdateSchema apenas com os dados filtrados
    tenant_update_schema_obj = schemas.TenantUpdateSchema(**filtered_update_data)

    conteudo_loja = None
    if loja_txt:
        conteudo_loja = await loja_txt.read()
        conteudo_loja = conteudo_loja.decode("utf-8")

    menu_image_url_to_update = None
    if menu_image:
        try:
            menu_image_url_to_update = await services.upload_image_to_supabase(menu_image)
            # Se o upload da nova imagem for bem-sucedido, tente deletar a imagem antiga
            if existing_tenant.menu_image_url: # Verifica se havia uma imagem antiga
                await services.delete_image_from_supabase(existing_tenant.menu_image_url)
        except HTTPException as e:
            raise e # Re-raise HTTPException from service layer
        except Exception as e:
            logger.error(f"Erro ao fazer upload da imagem do cardápio para o Supabase durante atualização: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Erro interno ao fazer upload da imagem do cardápio.")
    
    # Passar a instância do schema e a URL da imagem para a função crud.update_tenant
    updated_tenant = crud.update_tenant(db, tenant_id, tenant_update_schema_obj, conteudo_loja, menu_image_url_to_update)

    # Re-indexar informações da loja se foram atualizadas
    if conteudo_loja:
        try:
            loja_txt_path = f"temp_{tenant_id}_loja.txt"
            with open(loja_txt_path, "w", encoding="utf-8") as f:
                f.write(conteudo_loja)
            
            # Nota: a reindexação de produtos precisaria de um upload de Excel aqui.
            # Por enquanto, vamos reindexar apenas as informações da loja.
            services.load_data_to_vector_db(tenant_id, loja_txt_path, "") # Passa caminho vazio para produtos
            
            os.remove(loja_txt_path)
            logger.info(f"Informações da loja do tenant {tenant_id} re-indexadas no VectorDB.")
        except Exception as e:
            logger.error(f"Erro ao re-indexar dados para o tenant {tenant_id}: {e}", exc_info=True)

    return updated_tenant

@app.put("/tenants/{tenant_id}/toggle-status", dependencies=[Depends(get_current_user)])
def toggle_tenant_status(tenant_id: str, status_data: dict, db: Session = Depends(get_db)):
    return crud.toggle_tenant_status(db, tenant_id, status_data["is_active"])

@app.delete("/tenants/{tenant_id}", dependencies=[Depends(get_current_user)])
def delete_tenant(tenant_id: str, db: Session = Depends(get_db)):
    return crud.delete_tenant(db, tenant_id)

@app.get("/tenant-data/{tenant_id}", dependencies=[Depends(get_current_user)])
def get_tenant_data(tenant_id: str, db: Session = Depends(get_db)):
    """Endpoint para buscar dados específicos do tenant por tenant_id"""
    tenant = crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # A URL do endpoint de salvamento será a rota local /api/interactions
    salvar_banco_de_dados_url = "/api/interactions" # Pode ser uma URL completa se o frontend precisar
    
    return schemas.TenantDataResponse(
        tenantId=tenant.tenant_id,
        ID_pronpt=tenant.id_pronpt,
        url=tenant.url,
        evolutionApiKey=tenant.evolution_api_key,
        isActive=tenant.is_active,
        salvarBancoDeDados=salvar_banco_de_dados_url
    )

@app.post("/tenant-data/", response_model=schemas.TenantDataResponse, dependencies=[Depends(get_current_user)])
def get_tenant_data_by_instancia(request: schemas.TenantDataRequest, db: Session = Depends(get_db)):
    """Endpoint POST que recebe JSON com chave 'instancia' e retorna dados do tenant"""
    tenant = crud.get_tenant_by_id(db, tenant_id=request.instancia)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # A URL do endpoint de salvamento será a rota local /api/interactions
    salvar_banco_de_dados_url = "/api/interactions" # Pode ser uma URL completa se o frontend precisar
    
    return schemas.TenantDataResponse(
        tenantId=tenant.tenant_id,
        ID_pronpt=tenant.id_pronpt,
        url=tenant.url,
        evolutionApiKey=tenant.evolution_api_key,
        isActive=tenant.is_active,
        salvarBancoDeDados=salvar_banco_de_dados_url
    )

# =======================================================================
# Endpoint Principal da IA com CrewAI
# =======================================================================

@app.post("/ai", response_model=List[schemas.AIWebhookResponsePart], tags=["IA"])
async def handle_ai_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        request_body = await request.json()
        logger.info(f"RAW REQUEST BODY RECEIVED: {request_body}")
        
        # Validação manual para podermos logar o erro detalhado
        try:
            ai_request = schemas.AIWebhookRequest(**request_body)
            logger.info(f"Request body validated successfully: {ai_request.model_dump_json(indent=2)}")
        except ValidationError as e:
            logger.error(f"PYDANTIC VALIDATION ERROR: {e.errors()}", exc_info=True)
            raise HTTPException(status_code=422, detail=e.errors())

        tenant = await run_in_threadpool(crud.get_tenant_by_personality_name, db, personality_name=ai_request.personality_name)
        if not tenant:
            logger.error(f"Tenant com personality_name '{ai_request.personality_name}' não encontrado.")
            raise HTTPException(status_code=404, detail=f"Cliente com a personalidade '{ai_request.personality_name}' não foi encontrado.")

        personality_prompt = tenant.personality.prompt if tenant.personality and tenant.personality.prompt else "Você é um assistente de IA prestativo."
        
        logger.info(f"PROMPT EM USO: '{personality_prompt[:200]}...'")
        
        # Lógica para decodificar conteúdo de mídia se existir
        file_content = None
        mimetype = None
        if ai_request.message_base64 and ai_request.mimetype:
            try:
                file_content = base64.b64decode(ai_request.message_base64)
                mimetype = ai_request.mimetype
                logger.info(f"Mensagem com mídia recebida. Mimetype: {mimetype}, Tamanho: {len(file_content)} bytes")
            except Exception as e:
                logger.error(f"Erro ao decodificar a mensagem em base64: {e}", exc_info=True)
                # Decide se quer parar ou continuar sem a mídia
        
        ai_result = await services.handle_message(
            user_id=ai_request.user_phone,
            session_id=ai_request.whatsapp_message_id,
            message=ai_request.message_user,
            personality_name=ai_request.personality_name,
            personality_prompt=personality_prompt,
            file_content=file_content,
            mimetype=mimetype
        )

        logger.info(f"Resposta Estruturada da IA: {ai_result}")

        response_parts = []
        text_response = ai_result.get("response_text")
        human_handoff = ai_result.get("human_handoff", False)
        send_menu = ai_result.get("send_menu", False)

        if text_response:
            response_parts.append({
                "part_id": 1,
                "type": "text",
                "text_content": text_response,
                "human_handoff": False,
                "send_menu": False
            })

        if send_menu and tenant.menu_image_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(tenant.menu_image_url)
                    response.raise_for_status()
                    image_base64 = base64.b64encode(response.content).decode("utf-8")
                    mimetype, _ = mimetypes.guess_type(tenant.menu_image_url)

                response_parts.append({
                    "part_id": len(response_parts) + 1,
                    "type": "file",
                    "human_handoff": False,
                    "send_menu": True,
                    "file_details": {
                        "retrieval_key": "menu_image",
                        "file_type": mimetype or "image/jpeg",
                        "base64_content": image_base64
                    }
                })
            except Exception as e:
                logger.error(f"Erro ao baixar ou processar imagem do cardápio: {e}", exc_info=True)
        
        if human_handoff:
            response_parts.append({
                "part_id": len(response_parts) + 1,
                "type": "validation",
                "human_handoff": True,
                "send_menu": False
            })

        # Se não houver texto e nenhuma ação especial, retorna uma lista vazia ou uma resposta padrão
        if not response_parts:
            logger.warning("Nenhuma parte de resposta foi gerada pela IA.")
            # Opcional: retornar uma resposta padrão para evitar erro no cliente
            # response_parts.append(schemas.AIWebhookResponsePart(part_id=1, type="text", text_content="Não consegui processar sua solicitação."))

        return response_parts

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions para que o FastAPI as manipule
        raise http_exc
    except Exception as e:
        logger.critical(f"Erro crítico na rota /ai: {e}", exc_info=True)
        # Em vez de um detalhe genérico, podemos fornecer mais contexto se for seguro
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {str(e)}")

# =======================================================================
# Endpoint para Gerenciamento de Personalidades da IA
# =======================================================================

@app.post("/personalities/", response_model=schemas.Personality, tags=["Personalities"], dependencies=[Depends(get_current_user)])
def create_personality(personality: schemas.PersonalityCreate, db: Session = Depends(get_db)):
    logger.info(f"Tentando criar personalidade: {personality.name}")
    db_personality = crud.get_personality_by_name(db, name=personality.name)
    if db_personality:
        logger.warning(f"Tentativa de criar personalidade existente: {personality.name}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Personalidade com o nome '{personality.name}' já existe.")
    new_personality = crud.create_personality(db=db, personality=personality)
    logger.info(f"Personalidade {personality.name} criada com sucesso.")
    return new_personality

@app.get("/personalities/", response_model=List[schemas.Personality], tags=["Personalities"], dependencies=[Depends(get_current_user)])
def get_all_personalities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retorna todas as personalidades da IA."""
    personalities = crud.get_all_personalities(db, skip=skip, limit=limit)
    return personalities

@app.get("/personalities/{personality_name}", response_model=schemas.Personality, tags=["Personalities"], dependencies=[Depends(get_current_user)])
def get_personality_by_name(personality_name: str, db: Session = Depends(get_db)):
    """Retorna uma personalidade da IA pelo nome."""
    personality = crud.get_personality_by_name(db, name=personality_name)
    if personality is None:
        raise HTTPException(status_code=404, detail="Personalidade não encontrada")
    return personality

@app.put("/personalities/{personality_name}", response_model=schemas.Personality, tags=["Personalities"], dependencies=[Depends(get_current_user)])
def update_personality(personality_name: str, personality: schemas.PersonalityCreate, db: Session = Depends(get_db)):
    """Atualiza uma personalidade da IA existente."""
    db_personality = crud.get_personality_by_name(db, name=personality_name)
    if db_personality is None:
        raise HTTPException(status_code=404, detail="Personalidade não encontrada")
    
    # Se o nome foi alterado, verificar se o novo nome já existe
    if personality.name != personality_name and crud.get_personality_by_name(db, name=personality.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Já existe uma personalidade com o nome '{personality.name}'.")

    updated_personality = crud.update_personality(db, db_personality, personality)
    return updated_personality

@app.delete("/personalities/{personality_name}", tags=["Personalities"], dependencies=[Depends(get_current_user)])
def delete_personality(personality_name: str, db: Session = Depends(get_db)):
    """Deleta uma personalidade da IA."""
    personality = crud.get_personality_by_name(db, name=personality_name)
    if personality is None:
        raise HTTPException(status_code=404, detail="Personalidade não encontrada")
    crud.delete_personality(db, personality)
    return {"message": "Personalidade deletada com sucesso."}

# =======================================================================
# Endpoint para Recuperação de Arquivos
# =======================================================================

@app.get("/tenants/{tenant_id}/loja_txt", tags=["Tenants"], dependencies=[Depends(get_current_user)])
async def get_loja_txt(tenant_id: str, db: Session = Depends(get_db)):
    tenant = crud.get_tenant_by_id(db, tenant_id=tenant_id)
    if not tenant or not tenant.config_ai:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Informações da loja não encontradas.")
    return PlainTextResponse(content=tenant.config_ai, media_type="text/plain")

@app.get("/get-file/{retrieval_key}", tags=["Files"], dependencies=[Depends(get_current_user)])
def get_file(retrieval_key: str, db: Session = Depends(get_db)):
    logger.info(f"Requisição para recuperar arquivo: {retrieval_key}")
    # Em um cenário real, o arquivo seria buscado de um S3, Google Drive, etc.
    # e retornado com o content-type correto (e.g., image/png, application/pdf).

    # Simulação: verificar se a chave existe em algum produto
    product = crud.get_product_by_retrieval_key(db, retrieval_key=retrieval_key)

    if not product:
        logger.warning(f"Arquivo não encontrado para retrieval_key: {retrieval_key}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado com esta chave.")

    logger.info(f"Arquivo {product.name} encontrado para retrieval_key: {retrieval_key}")
    return {"message": f"Arquivo para a chave '{retrieval_key}' seria entregue aqui.", "product_name": product.name}

@app.post("/upload-products", tags=["Products"], dependencies=[Depends(get_current_user)])
async def upload_products(tenant_id: str, file: UploadFile, db: Session = Depends(get_db)):
    logger.info(f"Iniciando upload de produtos para tenant: {tenant_id}")
    try:
        products = await services.process_product_sheet(tenant_id, file, db)
        logger.info(f"{len(products)} produtos uploaded successfully for tenant: {tenant_id}")
        return {"message": f"{len(products)} products uploaded successfully."}
    except Exception as e:
        logger.error(f"Erro no upload de produtos para tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/products/{tenant_id}", response_model=List[schemas.Product], tags=["Products"], dependencies=[Depends(get_current_user)])
def get_products(tenant_id: str, db: Session = Depends(get_db)):
    logger.info(f"Buscando produtos para tenant: {tenant_id}")
    return crud.get_products_by_tenant_id(db, tenant_id=tenant_id)

@app.get("/products/{tenant_id}/download-excel", tags=["Products"], dependencies=[Depends(get_current_user)])
async def download_products_excel(tenant_id: str, db: Session = Depends(get_db)):
    logger.info(f"Gerando arquivo Excel de produtos para tenant: {tenant_id}")
    products = crud.get_products_by_tenant_id(db, tenant_id=tenant_id)
    
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum produto encontrado para este cliente.")

    # Criar um novo workbook e adicionar uma planilha
    wb = Workbook()
    ws = wb.active
    ws.title = "Produtos"

    # Adicionar cabeçalhos
    headers = [
        "Plano_(Produto)", 
        "Preço_Sugerido_(Mensal)", 
        "retrieval_key", 
        "tenant_id", 
        "Público-Alvo", 
        "Principais_Funcionalidades", 
        "Limitações/Observações", 
        "produto_promocao", 
        "preco_promotions", 
        "combo_product"
    ]
    ws.append(headers)

    # Adicionar os dados dos produtos
    for product in products:
        ws.append([
            product.name,
            product.price,
            product.retrieval_key,
            product.tenant_id,
            product.publico_alvo,
            product.principais_funcionalidades,
            product.limitacoes_observacoes,
            product.produto_promocao,
            product.preco_promotions,
            product.combo_product
        ])

    # Salvar o workbook em um buffer de bytes
    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    # Retornar o arquivo como um StreamingResponse
    filename = f"produtos_{tenant_id}.xlsx"
    return StreamingResponse(excel_file, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/calcular-frete", dependencies=[Depends(get_current_user)])
async def calcular_frete(
    tenant_id: str,
    cliente_lat: float,
    cliente_lng: float,
    db: Session = Depends(get_db)
):
    logger.info(f"Calculando frete para tenant {tenant_id} e cliente ({cliente_lat}, {cliente_lng})")
    # Buscar dados da loja (origem)
    tenant = crud.get_tenant_by_id(db, tenant_id)
    if not tenant:
        logger.warning(f"Tentativa de calcular frete para cliente não encontrado: {tenant_id}")
        raise HTTPException(status_code=404, detail="Cliente/loja não encontrado")
    
    if not tenant.latitude or not tenant.longitude:
        logger.warning(f"Loja {tenant_id} não possui coordenadas cadastradas para cálculo de frete.")
        raise HTTPException(status_code=400, detail="Loja não possui coordenadas cadastradas")
    
    if not GOOGLE_MAPS_API_KEY:
        logger.error("Google Maps API Key não configurada para cálculo de frete.")
        raise HTTPException(status_code=400, detail="Google Maps API Key não configurada")
    
    try:
        # Chamar a função assíncrona para calcular o frete
        distancia_km = await services.calcular_frete_google_maps_async(
            float(tenant.latitude), 
            float(tenant.longitude), 
            cliente_lat, 
            cliente_lng, 
            GOOGLE_MAPS_API_KEY
        )
        logger.info(f"Frete calculado para {tenant_id}: {distancia_km:.2f} km.")
        return {
            "distancia_km": distancia_km,
            "origem": {
                "endereco": tenant.endereco,
                "latitude": tenant.latitude,
                "longitude": tenant.longitude
            },
            "destino": {
                "latitude": cliente_lat,
                "longitude": cliente_lng
            }
        }
    except Exception as e:
        logger.error(f"Erro ao calcular frete para {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao calcular frete: {str(e)}")
