
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

class TenantCreate(BaseModel):
    tenant_id: str  # Instância
    nome_loja: str  # Nome da loja
    ia_personality: str # Nome da personalidade que será criada/atualizada
    ai_prompt_description: str # Descrição completa do prompt da IA
    endereco: str
    cep: str
    latitude: float
    longitude: float
    url: Optional[str] = None
    menu_image_url: Optional[str] = None # Adicionar no schema de criação, será a URL após upload

class Tenant(TenantBase):
    id: int
    nome_loja: str
    endereco: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    url: Optional[str] = None
    menu_image_url: Optional[str] = None # Adicionar aqui também para a resposta

    class Config:
        from_attributes = True

class TenantUpdateSchema(BaseModel):
    nome_loja: Optional[str] = None
    ia_personality: Optional[str] = None # Nome da personalidade que será atualizada
    ai_prompt_description: Optional[str] = None # Nova descrição do prompt da IA
    endereco: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    menu_image_url: Optional[str] = None # Adicionar no schema de atualização, será a URL após upload

class TenantConfigRequest(BaseModel):
    instancia: str

class TenantInstancia(BaseModel):
    instancia: str  # Chave "instancia" para primeira requisição
    url: str
    is_active: bool = True
    id_pronpt: str

class TenantDataRequest(BaseModel):
    instancia: str  # Chave "instancia" que será o tenant_id

class TenantDataResponse(BaseModel):
    tenant_id: str = Field(alias="tenantId") # Alterado para tenantId
    id_pronpt: str = Field(alias="ID_pronpt") # Alterado para ID_pronpt
    url: Optional[str] = None
    evolution_api_key: Optional[str] = Field(default=None, alias="evolutionApiKey") # Alterado para evolutionApiKey
    is_active: bool = Field(alias="isActive") # Alterado para isActive
    salvarBancoDeDados: str # Nova chave para a URL do endpoint de salvamento

# =======================================================================
# Esquemas para Personalidade da IA
# =======================================================================

class PersonalityBase(BaseModel):
    name: str
    prompt: str
    tenant_id: Optional[str] = None # Alterado para opcional

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
    message_user: Optional[str] = None
    message_base64: Optional[str] = None
    mimetype: Optional[str] = None
    personality_name: str
    user_phone: str
    whatsapp_message_id: str

class FileDetails(BaseModel):
    retrieval_key: str
    file_type: str
    base64_content: Optional[str] = None # Conteúdo da imagem em base64

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: str

class OrderDetails(BaseModel):
    order_id: str
    total_price: str
    items: List[OrderItem]

class AIWebhookResponsePart(BaseModel):
    part_id: int
    type: str
    text_content: Optional[str] = None
    file_details: Optional[FileDetails] = None
    human_handoff: bool = False # Flag por parte da mensagem
    send_menu: bool = False     # Flag por parte da mensagem

class AIProcessingResult(BaseModel):
    text_segments: List[str]
    human_handoff: bool
    send_menu: bool
    file_details: Optional[FileDetails] = None # Adicionado para retornar detalhes de arquivo da IA
    # Outros dados que a IA pode retornar, se necessário

class AIWebhookResponse(BaseModel):
    response_parts: List[AIWebhookResponsePart]
    # As flags human_handoff e send_menu foram movidas para AIWebhookResponsePart


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

# =======================================================================
# Esquemas para a Resposta Estruturada da IA
# =======================================================================
class AIResponse(BaseModel):
    response_text: str = Field(..., description="The final text response to send to the user.")
    human_handoff: bool = Field(description="Set to true ONLY if the user explicitly asks to speak to a human or is very frustrated.")
    send_menu: bool = Field(description="Set to true ONLY if the user asks for the menu or expresses clear intent to order.")
