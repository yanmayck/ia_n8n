from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

# =======================================================================
# Esquemas para Opcionais
# =======================================================================
class OpcionalBase(BaseModel):
    nome_opcional: str
    tipo_opcional: str
    preco_adicional: float = 0.0

class OpcionalCreate(OpcionalBase):
    pass

class OpcionalUpdate(OpcionalBase):
    pass

class Opcional(OpcionalBase):
    id_opcional: int
    tenant_id: str

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Promoções
# =======================================================================
class PromocaoBase(BaseModel):
    nome_promocao: str
    descricao_para_ia: Optional[str] = None
    condicao_json: Optional[Dict[str, Any]] = None
    acao_json: Optional[Dict[str, Any]] = None
    is_ativa: bool = True

class PromocaoCreate(PromocaoBase):
    pass

class PromocaoUpdate(PromocaoBase):
    pass

class Promocao(PromocaoBase):
    id_promocao: int
    tenant_id: str

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Produtos (Nova Estrutura)
# =======================================================================
class ProductBase(BaseModel):
    nome_produto: str
    descricao_produto: Optional[str] = None
    categoria_produto: Optional[str] = None
    preco_base: float
    tempo_preparo_min: Optional[int] = None
    disponivel_hoje: str = 'Sim'

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    pass

class Product(ProductBase):
    id_produto: int
    tenant_id: str
    opcionais: List[Opcional] = []
    promocoes: List[Promocao] = []

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Imagens de Cardápio
# =======================================================================
class MenuImageBase(BaseModel):
    image_url: str
    description: Optional[str] = None

class MenuImageCreate(MenuImageBase):
    pass

class MenuImage(MenuImageBase):
    id: int
    tenant_id: str

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Tenants (Clientes)
# =======================================================================
class TenantBase(BaseModel):
    tenant_id: str
    nome_loja: str
    config_ai: str
    evolution_api_key: Optional[str] = None
    is_active: bool = True
    id_pronpt: str

class TenantCreate(BaseModel):
    tenant_id: str
    nome_loja: str
    ia_personality: str
    ai_prompt_description: str
    endereco: str
    cep: str
    latitude: float
    longitude: float
    url: Optional[str] = None
    freight_config: Optional[str] = None

class Tenant(TenantBase):
    id: int
    endereco: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    url: Optional[str] = None
    menu_images: List[MenuImage] = []

    model_config = ConfigDict(from_attributes = True)

class TenantUpdateSchema(BaseModel):
    nome_loja: Optional[str] = None
    ia_personality: Optional[str] = None
    ai_prompt_description: Optional[str] = None
    endereco: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    freight_config: Optional[str] = None

class TenantConfigRequest(BaseModel):
    instancia: str

class TenantInstancia(BaseModel):
    instancia: str
    url: str
    is_active: bool = True
    id_pronpt: str

class TenantDataRequest(BaseModel):
    instancia: str

class TenantDataResponse(BaseModel):
    tenantId: str
    ID_pronpt: str
    url: Optional[str] = None
    evolutionApiKey: Optional[str] = None
    isActive: bool
    salvarBancoDeDados: str

# =======================================================================
# Esquemas para Personalidade da IA
# =======================================================================
class PersonalityBase(BaseModel):
    name: str
    prompt: str
    tenant_id: Optional[str] = None

class PersonalityCreate(PersonalityBase):
    pass

class Personality(PersonalityBase):
    id: int

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para o Webhook da IA (Entrada e Saída)
# =======================================================================
class AIWebhookRequest(BaseModel):
    message_user: Optional[str] = None
    message_base64: Optional[str] = None
    mimetype: Optional[str] = None
    tenant_id: str
    user_phone: str
    whatsapp_message_id: str
    latitude: Optional[Union[float, str]] = None
    longitude: Optional[Union[float, str]] = None

class FileDetails(BaseModel):
    retrieval_key: str
    file_type: str
    base64_content: Optional[str] = None

class AIWebhookResponsePart(BaseModel):
    part_id: int
    type: str
    text_content: Optional[str] = None
    file_details: Optional[FileDetails] = None
    human_handoff: bool = False
    send_menu: bool = False

class HumanHandoffOutput(BaseModel):
    should_handoff: bool

class MenuOutput(BaseModel):
    should_send_menu: bool

class FreightCalculationOutput(BaseModel):
    distance_km: float
    duration_minutes: float
    cost: Optional[float] = None

class FileUnderstandingOutput(BaseModel):
    summary: str
    file_type: str

class GeneralResponseOutput(BaseModel):
    text_response: str

class OrderItem(BaseModel):
    product_name: str
    quantity: int

class OrderTakingOutput(BaseModel):
    items: List[OrderItem]
    is_final_order: bool
    address: Optional[str] = None

class OrderState(BaseModel):
    items: List[OrderItem] = []
    address: Optional[str] = None
    status: str = "open"

# =======================================================================
# Esquemas para Interação com o Banco de Dados
# =======================================================================
class InteractionBase(BaseModel):
    user_phone: str
    whatsapp_message_id: str
    message_from_user: Optional[str] = None
    ai_response: Optional[str] = None
    personality_id: int
    tenant_id: str

class InteractionCreate(InteractionBase):
    pass

class Interaction(InteractionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Endereços de Usuários
# =======================================================================
class UserAddressBase(BaseModel):
    user_phone: str
    tenant_id: str
    address_text: str
    latitude: Optional[str] = None
    longitude: Optional[str] = None

class UserAddressCreate(UserAddressBase):
    pass

class UserAddress(UserAddressBase):
    id: int
    last_used_at: datetime

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Pedidos
# =======================================================================
class OrderBase(BaseModel):
    user_phone: str
    tenant_id: str
    items: List[Dict[str, Any]]
    total_price: str
    delivery_method: str
    address: Optional[str] = None
    freight_details: Optional[Dict[str, Any]] = None

class OrderCreate(OrderBase):
    pass

class Order(OrderBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para a Resposta Estruturada da IA
# =======================================================================
class FreightDetails(BaseModel):
    distance_km: float
    origin_address: Optional[str] = None
    origin_latitude: Optional[float] = None
    origin_longitude: Optional[float] = None
    destination_latitude: float
    destination_longitude: float
    cost: Optional[float] = None

class FileSummary(BaseModel):
    summary_text: str
    file_type: str

class AIResponse(BaseModel):
    response_text: str
    human_handoff: bool
    send_menu: bool
    freight_details: Optional[FreightDetails] = None
    file_summary: Optional[FileSummary] = None

class OrchestratorDecision(BaseModel):
    agent_to_call: str
    agent_input: Optional[str] = None

class FinalResponseData(BaseModel):
    text_response: str
    human_handoff_needed: bool = False
    send_menu_requested: bool = False
    freight_details: Optional[FreightDetails] = None
    file_summary: Optional[FileSummary] = None

# =======================================================================
# Novos Esquemas para Análise de Intenção da IA
# =======================================================================
class TarefaIdentificada(BaseModel):
    tipo_tarefa: str = Field(description="O tipo de tarefa, como 'adicionar_item', 'verificar_promocao', 'fazer_pergunta_geral'.")
    detalhes: Optional[str] = Field(description="Os detalhes específicos da tarefa, como o nome do produto ou a pergunta feita.")

class AnaliseDeIntencao(BaseModel):
    tarefas: List[TarefaIdentificada] = Field(description="Uma lista de todas as tarefas que o usuário quer executar.")
    contem_urgencia: bool = Field(description="Verdadeiro se o usuário parece apressado ou frustrado.")

# =======================================================================
# Esquemas para Produtos (Nova Estrutura)
# =======================================================================
class ProductBase(BaseModel):
    nome_produto: str
    descricao_produto: Optional[str] = None
    categoria_produto: Optional[str] = None
    preco_base: float
    tempo_preparo_min: Optional[int] = None
    disponivel_hoje: str = 'Sim'

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    pass

class Product(ProductBase):
    id_produto: int
    tenant_id: str
    opcionais: List[Opcional] = []
    promocoes: List[Promocao] = []

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Imagens de Cardápio
# =======================================================================
class MenuImageBase(BaseModel):
    image_url: str
    description: Optional[str] = None

class MenuImageCreate(MenuImageBase):
    pass

class MenuImage(MenuImageBase):
    id: int
    tenant_id: str

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Tenants (Clientes)
# =======================================================================
class TenantBase(BaseModel):
    tenant_id: str
    nome_loja: str
    config_ai: str
    evolution_api_key: Optional[str] = None
    is_active: bool = True
    id_pronpt: str

class TenantCreate(BaseModel):
    tenant_id: str
    nome_loja: str
    ia_personality: str
    ai_prompt_description: str
    endereco: str
    cep: str
    latitude: float
    longitude: float
    url: Optional[str] = None
    freight_config: Optional[str] = None

class Tenant(TenantBase):
    id: int
    endereco: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    url: Optional[str] = None
    menu_images: List[MenuImage] = []

    model_config = ConfigDict(from_attributes = True)

class TenantUpdateSchema(BaseModel):
    nome_loja: Optional[str] = None
    ia_personality: Optional[str] = None
    ai_prompt_description: Optional[str] = None
    endereco: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    freight_config: Optional[str] = None

class TenantConfigRequest(BaseModel):
    instancia: str

class TenantInstancia(BaseModel):
    instancia: str
    url: str
    is_active: bool = True
    id_pronpt: str

class TenantDataRequest(BaseModel):
    instancia: str

class TenantDataResponse(BaseModel):
    tenantId: str
    ID_pronpt: str
    url: Optional[str] = None
    evolutionApiKey: Optional[str] = None
    isActive: bool
    salvarBancoDeDados: str

# =======================================================================
# Esquemas para Personalidade da IA
# =======================================================================
class PersonalityBase(BaseModel):
    name: str
    prompt: str
    tenant_id: Optional[str] = None

class PersonalityCreate(PersonalityBase):
    pass

class Personality(PersonalityBase):
    id: int

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para o Webhook da IA (Entrada e Saída)
# =======================================================================
class AIWebhookRequest(BaseModel):
    message_user: Optional[str] = None
    message_base64: Optional[str] = None
    mimetype: Optional[str] = None
    tenant_id: str
    user_phone: str
    whatsapp_message_id: str
    latitude: Optional[Union[float, str]] = None
    longitude: Optional[Union[float, str]] = None

class FileDetails(BaseModel):
    retrieval_key: str
    file_type: str
    base64_content: Optional[str] = None

class AIWebhookResponsePart(BaseModel):
    part_id: int
    type: str
    text_content: Optional[str] = None
    file_details: Optional[FileDetails] = None
    human_handoff: bool = False
    send_menu: bool = False

class HumanHandoffOutput(BaseModel):
    should_handoff: bool

class MenuOutput(BaseModel):
    should_send_menu: bool

class FreightCalculationOutput(BaseModel):
    distance_km: float
    duration_minutes: float
    cost: Optional[float] = None

class FileUnderstandingOutput(BaseModel):
    summary: str
    file_type: str

class GeneralResponseOutput(BaseModel):
    text_response: str

class OrderItem(BaseModel):
    product_name: str
    quantity: int

class OrderTakingOutput(BaseModel):
    items: List[OrderItem]
    is_final_order: bool
    address: Optional[str] = None

class OrderState(BaseModel):
    items: List[OrderItem] = []
    address: Optional[str] = None
    status: str = "open"

# =======================================================================
# Esquemas para Interação com o Banco de Dados
# =======================================================================
class InteractionBase(BaseModel):
    user_phone: str
    whatsapp_message_id: str
    message_from_user: Optional[str] = None
    ai_response: Optional[str] = None
    personality_id: int
    tenant_id: str

class InteractionCreate(InteractionBase):
    pass

class Interaction(InteractionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Endereços de Usuários
# =======================================================================
class UserAddressBase(BaseModel):
    user_phone: str
    tenant_id: str
    address_text: str
    latitude: Optional[str] = None
    longitude: Optional[str] = None

class UserAddressCreate(UserAddressBase):
    pass

class UserAddress(UserAddressBase):
    id: int
    last_used_at: datetime

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para Pedidos
# =======================================================================
class OrderBase(BaseModel):
    user_phone: str
    tenant_id: str
    items: List[Dict[str, Any]]
    total_price: str
    delivery_method: str
    address: Optional[str] = None
    freight_details: Optional[Dict[str, Any]] = None

class OrderCreate(OrderBase):
    pass

class Order(OrderBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes = True)

# =======================================================================
# Esquemas para a Resposta Estruturada da IA
# =======================================================================
class FreightDetails(BaseModel):
    distance_km: float
    origin_address: Optional[str] = None
    origin_latitude: Optional[float] = None
    origin_longitude: Optional[float] = None
    destination_latitude: float
    destination_longitude: float
    cost: Optional[float] = None

class FileSummary(BaseModel):
    summary_text: str
    file_type: str

class AIResponse(BaseModel):
    response_text: str
    human_handoff: bool
    send_menu: bool
    freight_details: Optional[FreightDetails] = None
    file_summary: Optional[FileSummary] = None

class OrchestratorDecision(BaseModel):
    agent_to_call: str
    agent_input: Optional[str] = None