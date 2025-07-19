
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, unique=True, index=True, nullable=False)
    config_ai = Column(Text, nullable=False)
    evolution_api_key = Column(String)
    is_active = Column(Boolean, default=True)
    salvar_banco_de_dados_url = Column(String)
    id_pronpt = Column(String, ForeignKey("personalities.name"))

    personality = relationship("Personality")

class Personality(Base):
    __tablename__ = "personalities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    prompt = Column(Text, nullable=False)

    interactions = relationship("Interaction", back_populates="personality")

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, index=True, nullable=False)
    whatsapp_message_id = Column(String, unique=True, nullable=False)
    message_from_user = Column(Text)
    ai_response = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    personality_id = Column(Integer, ForeignKey("personalities.id"))
    personality = relationship("Personality", back_populates="interactions")
