from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, JSON, Table, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

# Tabela de Associação: Produto <-> Opcional
produto_opcional_association = Table('produto_opcional', Base.metadata,
    Column('produto_id', Integer, ForeignKey('produtos.id_produto')),
    Column('opcional_id', Integer, ForeignKey('opcionais.id_opcional'))
)

# Tabela de Associação: Produto <-> Promocao
produto_promocao_association = Table('produto_promocao', Base.metadata,
    Column('produto_id', Integer, ForeignKey('produtos.id_produto')),
    Column('promocao_id', Integer, ForeignKey('promocoes.id_promocao'))
)

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, unique=True, index=True, nullable=False)
    nome_loja = Column(String, nullable=False)
    config_ai = Column(Text, nullable=False)
    evolution_api_key = Column(String)
    is_active = Column(Boolean, default=True)
    id_pronpt = Column(Integer)
    endereco = Column(String)
    cep = Column(String)
    latitude = Column(String)
    longitude = Column(String)
    url = Column(String)
    freight_config = Column(Text, nullable=True)
    
    personality_id = Column(Integer, ForeignKey("personalities.id"))
    personality = relationship("Personality")

class MenuImage(Base):
    __tablename__ = "menu_images"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    image_url = Column(String, nullable=False)
    description = Column(String) # Ex: "Cardápio Principal", "Promoções da Semana"

class Personality(Base):
    __tablename__ = "personalities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    prompt = Column(Text, nullable=False)

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, index=True, nullable=False)
    whatsapp_message_id = Column(String, unique=True, nullable=False)
    message_from_user = Column(Text)
    ai_response = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    personality_id = Column(Integer, ForeignKey("personalities.id"))
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)

class Product(Base):
    __tablename__ = "produtos" # Nome da tabela alterado

    id_produto = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    nome_produto = Column(String, index=True, nullable=False)
    descricao_produto = Column(Text, nullable=True)
    categoria_produto = Column(String, index=True)
    preco_base = Column(Float, nullable=False)
    tempo_preparo_min = Column(Integer)
    disponivel_hoje = Column(String, default='Sim') # Sim/Não

    opcionais = relationship("Opcional", secondary=produto_opcional_association, back_populates="produtos")
    promocoes = relationship("Promocao", secondary=produto_promocao_association, back_populates="produtos")

class Opcional(Base):
    __tablename__ = "opcionais"

    id_opcional = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    nome_opcional = Column(String, nullable=False)
    tipo_opcional = Column(String, nullable=False)  # "Adicional" ou "Remoção"
    preco_adicional = Column(Float, default=0.0)

    produtos = relationship("Product", secondary=produto_opcional_association, back_populates="opcionais")

class Promocao(Base):
    __tablename__ = "promocoes"

    id_promocao = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    nome_promocao = Column(String, nullable=False)
    descricao_para_ia = Column(Text, nullable=True) # Novo campo para o roteiro da IA
    condicao_json = Column(JSON, nullable=True) # Novo campo para a lógica da condição
    acao_json = Column(JSON, nullable=True) # Novo campo para a lógica da ação
    is_ativa = Column(Boolean, default=True) # Novo campo para ativar/desativar

    produtos = relationship("Product", secondary=produto_promocao_association, back_populates="promocoes")

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
    delivery_method = Column(String, nullable=False)
    address = Column(Text, nullable=True)
    freight_details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    