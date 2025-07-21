
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, unique=True, index=True, nullable=False)  # Instância
    nome_loja = Column(String, nullable=False)  # Nome da loja para identificação
    config_ai = Column(Text, nullable=False)  # Descrição da empresa
    evolution_api_key = Column(String)
    is_active = Column(Boolean, default=True)
    id_pronpt = Column(String, ForeignKey("personalities.name"))
    endereco = Column(String)
    cep = Column(String)
    latitude = Column(String)
    longitude = Column(String)
    url = Column(String)  # URL da instância
    menu_image_url = Column(String, nullable=True) # Nova coluna para a URL da imagem do cardápio

    personality = relationship("Personality", foreign_keys=[id_pronpt])

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
    personality = relationship("Personality", back_populates="interactions")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    price = Column(String, nullable=False)
    retrieval_key = Column(String, unique=True, index=True, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"))
    
    # Novas colunas para os dados do Excel
    publico_alvo = Column(Text, nullable=True) # Coluna para 'Público-Alvo'
    principais_funcionalidades = Column(Text, nullable=True) # Coluna para 'Principais Funcionalidades'
    limitacoes_observacoes = Column(Text, nullable=True) # Coluna para 'Limitações / Observações'
    produto_promocao = Column(Boolean, nullable=True) # Coluna para 'produto_promocao'
    preco_promotions = Column(String, nullable=True) # Coluna para 'preco_promotions'
    combo_product = Column(String, nullable=True) # Coluna para 'combo_product'

    tenant = relationship("Tenant")
