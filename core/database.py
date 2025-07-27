
import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não está definida no arquivo .env")

connect_args = {}
# Se estiver usando SQLite, precisa permitir que a conexão seja usada em múltiplos threads.
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Para PostgreSQL, ao usar o pooler do Supabase (PgBouncer),
# é necessário desativar o pooling do SQLAlchemy (poolclass=NullPool)
# e desativar "prepared statements" (prepare_threshold: None), que não são suportados.
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args={"prepare_threshold": None}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args=connect_args
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
