
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, unique=True, index=True, nullable=False)
    nome_loja = Column(String, nullable=False)
    config_ai = Column(Text, nullable=False)
    evolution_api_key = Column(String)
    is_active = Column(Boolean, default=True)
    id_pronpt = Column(String, ForeignKey("personalities.name"))
    endereco = Column(String)
    cep = Column(String)
    latitude = Column(String)
    longitude = Column(String)
    url = Column(String)
    menu_image_url = Column(String, nullable=True)
    freight_config = Column(Text, nullable=True)

    personality = relationship("Personality", foreign_keys=[id_pronpt])
    orders = relationship("Order", back_populates="tenant")

class Personality(Base):
    __tablename__ = "personalities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    prompt = Column(Text, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))

    interactions = relationship("Interaction", back_populates="personality")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, index=True, nullable=False)
    whatsapp_message_id = Column(String, unique=True, nullable=False)
    message_from_user = Column(Text)
    ai_response = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    personality_id = Column(Integer, ForeignKey("personalities.id"))
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False) # Adicionado tenant_id

    personality = relationship("Personality", back_populates="interactions")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    price = Column(String, nullable=False)
    retrieval_key = Column(String, unique=True, index=True, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    
    publico_alvo = Column(Text, nullable=True)
    principais_funcionalidades = Column(Text, nullable=True)
    limitacoes_observacoes = Column(Text, nullable=True)
    produto_promocao = Column(Boolean, nullable=True)
    preco_promotions = Column(String, nullable=True)
    combo_product = Column(String, nullable=True)
    tempo_preparo_minutos = Column(Integer, nullable=True)

    tenant = relationship("Tenant")

class UserAddress(Base):
    __tablename__ = "user_addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, index=True, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    address_text = Column(Text, nullable=False)
    latitude = Column(String, nullable=True)
    longitude = Column(String, nullable=True)
    last_used_at = Column(DateTime(timezone=True), server_default=func.now())

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, index=True, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    items = Column(JSON, nullable=False)
    total_price = Column(String, nullable=False)
    delivery_method = Column(String, nullable=False) # "entrega" ou "retirada"
    address = Column(Text, nullable=True) # Nullable para caso de retirada
    freight_details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="orders")
