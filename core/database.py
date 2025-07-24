
import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não está definida no arquivo .env")


# Para PostgreSQL, ao usar o pooler do Supabase (PgBouncer),
# é necessário desativar o pooling do SQLAlchemy (poolclass=NullPool)
# e desativar "prepared statements" (prepare_threshold: None), que não são suportados.
logging.info(f"DATABASE_URL: {DATABASE_URL}")
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={"prepare_threshold": None}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
