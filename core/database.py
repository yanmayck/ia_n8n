
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_NAME = os.getenv("POSTGRES_DB")
SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")

# Verifica se todas as variáveis necessárias estão presentes
if not all([DB_USER, DB_PASSWORD, SUPABASE_PROJECT_REF, DB_NAME]):
    raise ValueError("Por favor, configure POSTGRES_USER, POSTGRES_PASSWORD, SUPABASE_PROJECT_REF e POSTGRES_DB no seu arquivo .env")

# --- Conexão via Transaction Pooler (Compatível com IPv4/Docker) ---
# Hostname estático para o pooler da região sa-east-1
DB_HOST = f"aws-0-sa-east-1.pooler.supabase.com"
# A referência do projeto é anexada ao usuário
FULL_DB_USER = f"{DB_USER}.{SUPABASE_PROJECT_REF}"
# Porta do Transaction Pooler
DB_PORT = "6543"

# Constrói a URL de conexão final para o Transaction Pooler.
DATABASE_URL = f"postgresql://{FULL_DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# Para PostgreSQL, ao usar o pooler do Supabase (PgBouncer),
# é necessário desativar o pooling do SQLAlchemy (poolclass=NullPool)
# e desativar "prepared statements" (prepare_threshold: None), que não são suportados.
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={"prepare_threshold": None}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
