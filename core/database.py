import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "A variável de ambiente DATABASE_URL não está definida no arquivo .env"
    )

connect_args = {}

# Configuração do engine baseada no tipo de banco de dados
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, poolclass=NullPool, connect_args=connect_args)
elif DATABASE_URL.startswith("postgresql"):
    # Para PostgreSQL, ao usar o pooler do Supabase (PgBouncer),
    # é necessário desativar o pooling do SQLAlchemy (poolclass=NullPool)
    # e desativar "prepared statements" (prepare_threshold: None), que não são suportados.
    # Adicionando timeouts para conexão
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args={
            "prepare_threshold": None,
            "connect_timeout": 5,  # Timeout para estabelecer a conexão física
        },
    )
else:
    # Configuração genérica para outros bancos de dados
    engine = create_engine(DATABASE_URL, poolclass=NullPool, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

logger.info(
    f"SQLAlchemy Engine configurado para {DATABASE_URL} com timeouts (se aplicável)."
)
