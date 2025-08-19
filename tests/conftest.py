import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os
import sys
from unittest.mock import patch
from dotenv import load_dotenv
import redis
import logging

# --- CONFIGURAÇÃO DO AMBIENTE DE TESTE ---
# Este bloco é executado ANTES de qualquer outra importação ou fixture.

# 1. Define o diretório raiz do projeto (ia_n8n)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# 2. Adiciona a raiz ao sys.path para que as importações funcionem
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 3. Carrega as variáveis de ambiente do .env.test
dotenv_path = os.path.join(project_root, '.env.test')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv(dotenv_path=".env.test")

# 4. AGORA, com o ambiente configurado, podemos importar os módulos da aplicação
from core.database import Base
from api.dependencies import get_db
from api.main import app
from core import models, schemas
from crud import tenant_crud
from services import data_sync_service

# --- USAR A URL DE TESTE ---
TEST_DATABASE_URL = os.getenv("DATABASE_URL")
if not TEST_DATABASE_URL:
    raise ValueError("DATABASE_URL não encontrada no arquivo .env.test. Verifique o caminho e a configuração.")

logger = logging.getLogger(__name__)

# Engine é criado uma vez para toda a sessão de testes
engine = create_engine(TEST_DATABASE_URL)

# Session factory
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FIXTURES DO PYTEST ---

from alembic.config import Config
from alembic import command

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Aplica as migrações do Alembic no início da sessão de testes e as reverte no final.
    """
    alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(project_root, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    command.upgrade(alembic_cfg, "head")
    yield
    command.downgrade(alembic_cfg, "base")
    engine.dispose()

@pytest.fixture(scope="function", autouse=True)
def clear_redis_cache():
    """
    Fixture para limpar o cache do Redis de teste antes de cada teste.
    O autouse=True garante que será executado para cada função de teste.
    """
    logger.info("FIXTURE_TRACE: Limpando o cache do Redis de teste.")
    try:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT"))
        redis_password = os.getenv("REDIS_PASSWORD") or None
        
        r = redis.Redis(host=redis_host, port=redis_port, password=redis_password)
        r.flushdb()
        logger.info("FIXTURE_TRACE: Cache do Redis limpo com sucesso.")
    except (redis.exceptions.ConnectionError, TypeError) as e:
        logger.error(f"FIXTURE_TRACE: Não foi possível conectar ao Redis para limpar o cache: {e}")
        pytest.fail(f"Não foi possível conectar ao Redis em {redis_host}:{redis_port}. O teste não pode continuar.")
    
    yield

@pytest.fixture(scope="function")
def db_session(clear_redis_cache):
    """
    Cria uma nova sessão de banco de dados para cada teste, dentro de uma transação.
    A transação é revertida no final do teste, isolando-o.
    """
    logger.info("FIXTURE_TRACE: 1. Entrando na fixture db_session.")
    connection = engine.connect()
    logger.info("FIXTURE_TRACE: 2. Conexão com o engine estabelecida.")
    transaction = connection.begin()
    logger.info("FIXTURE_TRACE: 3. Transação iniciada.")
    session = TestingSessionLocal(bind=connection)
    logger.info("FIXTURE_TRACE: 4. Sessão de teste criada e pronta para ser entregue (yield).")
    
    try:
        yield session
    finally:
        logger.info("FIXTURE_TRACE: 5. Teste concluído, iniciando limpeza da fixture.")
        session.close()
        logger.info("FIXTURE_TRACE: 6. Sessão fechada.")
        transaction.rollback()
        logger.info("FIXTURE_TRACE: 7. Transação revertida (rollback).")
        connection.close()
        logger.info("FIXTURE_TRACE: 8. Conexão com o engine fechada. Fim da fixture.")

import httpx

@pytest.fixture(scope="function")
async def client(db_session: Session):
    """
    Cria um cliente de teste assíncrono para a API e sobrescreve a dependência do DB
    para usar a sessão de teste transacional.
    """
    os.chdir(project_root)
    
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client
        
    del app.dependency_overrides[get_db]

@pytest.fixture(scope="function")
async def test_tenant(db_session: Session):
    """Cria um tenant de teste e carrega seus dados no VectorDB."""
    personality_data = schemas.PersonalityCreate(name="test_personality_for_tenant", prompt="Prompt de teste.")
    db_personality = models.Personality(name=personality_data.name, prompt=personality_data.prompt)
    db_session.add(db_personality)
    db_session.commit()
    db_session.refresh(db_personality)

    tenant_data = schemas.TenantCreate(
        tenant_id="test_tenant_id",
        nome_loja="Loja de Teste",
        ia_personality=db_personality.name,
        ai_prompt_description="Descrição de teste",
        endereco="Rua Teste, 123",
        cep="12345-678",
        latitude=-23.550520,
        longitude=-46.633308,
        url="http://test.com",
        freight_config='{"type": "FIXED", "price": 12.50}'
    )
    conteudo_loja_para_teste = """
    Informações da loja de teste:
    Nossa pizzaria funciona todos os dias das 11h às 23h.
    Oferecemos pizzas deliciosas e promoções incríveis.
    """
    tenant = tenant_crud.create_tenant(db_session, tenant_data, conteudo_loja=conteudo_loja_para_teste)
    
    await data_sync_service.load_data_to_vector_db(db_session, tenant.tenant_id)
    
    return tenant