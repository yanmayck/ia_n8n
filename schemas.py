
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# =======================================================================
# Esquemas para Tenants (Clientes)
# =======================================================================

class TenantBase(BaseModel):
    tenant_id: str
    config_ai: str
    evolution_api_key: Optional[str] = None
    is_active: bool = True
    id_pronpt: str

class TenantCreate(TenantBase):
    pass

class Tenant(TenantBase):
    id: int

    class Config:
        from_attributes = True

class TenantConfigRequest(BaseModel):
    instancia: str

# =======================================================================
# Esquemas para Personalidade da IA
# =======================================================================

class PersonalityBase(BaseModel):
    name: str
    prompt: str
    tenant_id: str

class PersonalityCreate(PersonalityBase):
    pass

class Personality(PersonalityBase):
    id: int

    class Config:
        from_attributes = True

# =======================================================================
# Esquemas para o Webhook da IA (Entrada e Saída)
# =======================================================================

class AIWebhookRequest(BaseModel):
    message_user: Optional[str] = Field(default=None, alias="mensege_user")
    message_base64: Optional[str] = Field(default=None, alias="mensege_bese64")
    mimetype: Optional[str] = Field(default=None)
    personality_name: str = Field(alias="pronpt_cliente")
    user_phone: str = Field(default="unknown_user", alias="user_phone")
    whatsapp_message_id: str = Field(default="unknown_wpp_id", alias="whatsapp_message_id")

class FileDetails(BaseModel):
    retrieval_key: str
    file_type: str

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: str

class OrderDetails(BaseModel):
    order_id: str
    total_price: str
    items: List[OrderItem]

class AIWebhookResponse(BaseModel):
    part_id: int
    type: str
    text_content: str
    file_details: Optional[FileDetails] = None
    order_details: Optional[OrderDetails] = None


# =======================================================================
# Esquemas para Produtos
# =======================================================================

class ProductBase(BaseModel):
    name: str
    price: str
    retrieval_key: str
    tenant_id: str

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int

    class Config:
        from_attributes = True

# =======================================================================
# Esquemas para Interação com o Banco de Dados
# =======================================================================

class InteractionBase(BaseModel):
    user_phone: str
    whatsapp_message_id: str
    message_from_user: Optional[str] = None
    ai_response: Optional[str] = None
    personality_id: int

class InteractionCreate(InteractionBase):
    pass

class Interaction(InteractionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
