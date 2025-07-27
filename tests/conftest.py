import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os
import sys
from dotenv import load_dotenv

# --- CARREGAR O ARQUIVO DE AMBIENTE DE TESTE PRIMEIRO ---
load_dotenv(dotenv_path=".env.test")

# Adiciona o diretório raiz ao path para encontrar os módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import Base
from alembic.config import Config
from alembic import command

# Importa Base e get_db DEPOIS de definir a DATABASE_URL
from api.dependencies import get_db
from api.main import app
from core import models, schemas
from crud import tenant_crud

# --- USAR A URL DE TESTE ---
TEST_DATABASE_URL = os.getenv("DATABASE_URL")
if not TEST_DATABASE_URL:
    raise ValueError("DATABASE_URL não encontrada no arquivo .env.test. Verifique o caminho.")

# Engine é criado uma vez para toda a sessão de testes
engine = create_engine(TEST_DATABASE_URL)

# Session factory
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Cria as tabelas uma vez no início da sessão de testes
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Garante que o banco de dados esteja limpo antes de iniciar e após a execução
    Base.metadata.drop_all(bind=engine)
    # Cria o schema do banco de dados com base nos modelos atuais
    Base.metadata.create_all(bind=engine)
    
    yield # Os testes rodam aqui
    
    # Limpa o banco de dados após a sessão de testes
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """
    Cria uma nova sessão de banco de dados para cada teste, dentro de uma transação.
    A transação é revertida no final do teste, isolando-o.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Cria um cliente de teste para a API e sobrescreve a dependência do DB
    para usar a sessão de teste transacional.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]

@pytest.fixture(scope="function")
def test_tenant(db_session: Session):
    """Cria um tenant de teste para ser usado nos testes."""
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
        freight_config="{}"
    )
    tenant = tenant_crud.create_tenant(db_session, tenant_data, conteudo_loja="Conteúdo de loja de teste")
    return tenant