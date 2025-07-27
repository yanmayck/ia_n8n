import pytest
from sqlalchemy.orm import Session
from core import models, schemas
from crud import tenant_crud, product_crud, opcional_crud, promocao_crud

# Testes para Tenant CRUD
def test_create_tenant(db_session: Session):
    personality_data = schemas.PersonalityCreate(name="test_personality", prompt="test prompt")
    tenant_data = schemas.TenantCreate(
        tenant_id="test_tenant",
        nome_loja="Test Store",
        ia_personality=personality_data.name,
        ai_prompt_description=personality_data.prompt,
        endereco="123 Test St",
        cep="12345-678",
        latitude=-23.550520,
        longitude=-46.633308
    )
    conteudo_loja = "Informações da loja de teste."
    
    tenant = tenant_crud.create_tenant(db_session, tenant_data, conteudo_loja)
    
    assert tenant.tenant_id == "test_tenant"
    assert tenant.nome_loja == "Test Store"
    assert tenant.config_ai == conteudo_loja
    assert tenant.personality is not None
    assert tenant.personality.name == "test_personality"

def test_get_tenant_by_id(db_session: Session):
    # Primeiro, crie um tenant para buscar
    personality_data = schemas.PersonalityCreate(name="get_test_personality", prompt="get prompt")
    tenant_data = schemas.TenantCreate(
        tenant_id="get_test_tenant",
        nome_loja="Get Test Store",
        ia_personality=personality_data.name,
        ai_prompt_description=personality_data.prompt,
        endereco="456 Get St",
        cep="87654-321",
        latitude=-10.916449,
        longitude=-37.074795
    )
    conteudo_loja = "Info para get."
    tenant_crud.create_tenant(db_session, tenant_data, conteudo_loja)

    fetched_tenant = tenant_crud.get_tenant_by_id(db_session, "get_test_tenant")
    assert fetched_tenant is not None
    assert fetched_tenant.tenant_id == "get_test_tenant"


def test_get_all_tenants(db_session: Session):
    # Conta os tenants existentes (pode haver tenants de outros testes, como o test_tenant fixture)
    initial_tenants = db_session.query(models.Tenant).count()

    # Crie alguns tenants
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="tenant1", nome_loja="Loja 1", ia_personality="p1", ai_prompt_description="desc1", endereco="e1", cep="c1", latitude=1.0, longitude=1.0), "config1")
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="tenant2", nome_loja="Loja 2", ia_personality="p2", ai_prompt_description="desc2", endereco="e2", cep="c2", latitude=2.0, longitude=2.0), "config2")
    
    # Verifica se a contagem aumentou em 2
    assert db_session.query(models.Tenant).count() == initial_tenants + 2

def test_update_tenant(db_session: Session):
    # Crie um tenant para atualizar
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="update_tenant", nome_loja="Old Name", ia_personality="old_p", ai_prompt_description="old_desc", endereco="old_e", cep="old_c", latitude=0.0, longitude=0.0), "old_config")
    
    update_data = schemas.TenantUpdateSchema(nome_loja="New Name", ia_personality="old_p", ai_prompt_description="new_desc", is_active=False)
    updated_tenant = tenant_crud.update_tenant(db_session, "update_tenant", update_data, "new_config")
    
    assert updated_tenant.nome_loja == "New Name"
    assert updated_tenant.config_ai == "new_config"
    assert updated_tenant.is_active == False
    assert updated_tenant.personality.prompt == "new_desc"

def test_delete_tenant(db_session: Session):
    # Crie um tenant para deletar
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="delete_tenant", nome_loja="Delete Me", ia_personality="del_p", ai_prompt_description="del_desc", endereco="del_e", cep="del_c", latitude=0.0, longitude=0.0), "del_config")
    
    result = tenant_crud.delete_tenant(db_session, "delete_tenant")
    assert result == {"message": "Cliente removido com sucesso"}
    assert tenant_crud.get_tenant_by_id(db_session, "delete_tenant") is None

def test_toggle_tenant_status(db_session: Session):
    # Crie um tenant para alternar o status
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="toggle_tenant", nome_loja="Toggle Me", ia_personality="tog_p", ai_prompt_description="tog_desc", endereco="tog_e", cep="tog_c", latitude=0.0, longitude=0.0), "tog_config")
    
    toggled_tenant = tenant_crud.toggle_tenant_status(db_session, "toggle_tenant", False)
    assert toggled_tenant.is_active == False
    
    toggled_tenant = tenant_crud.toggle_tenant_status(db_session, "toggle_tenant", True)
    assert toggled_tenant.is_active == True

def test_create_tenant_instancia(db_session: Session):
    tenant_instancia_data = schemas.TenantInstancia(
        instancia="instancia_test",
        url="http://test.com",
        is_active=True,
        id_pronpt="instancia_personality"
    )
    
    tenant = tenant_crud.create_tenant_instancia(db_session, tenant_instancia_data)
    
    assert tenant.tenant_id == "instancia_test"
    assert tenant.url == "http://test.com"
    assert tenant.is_active == True
    assert tenant.personality.name == "instancia_personality"

# Testes para Product CRUD
def test_create_product(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="prod_tenant", nome_loja="Prod Store", ia_personality="prod_p", ai_prompt_description="prod_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "prod_config")
    product_data = schemas.ProductCreate(nome_produto="Pizza", descricao_produto="Deliciosa", categoria_produto="Comida", preco_base=30.0, tempo_preparo_min=20, disponivel_hoje="Sim")
    
    product = product_crud.create_product(db_session, product_data, "prod_tenant")
    
    assert product.nome_produto == "Pizza"
    assert product.tenant_id == "prod_tenant"

def test_get_product(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="get_prod_tenant", nome_loja="Get Prod Store", ia_personality="get_prod_p", ai_prompt_description="get_prod_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "get_prod_config")
    product_data = schemas.ProductCreate(nome_produto="Burger", preco_base=25.0)
    created_product = product_crud.create_product(db_session, product_data, "get_prod_tenant")
    
    fetched_product = product_crud.get_product(db_session, created_product.id_produto)
    assert fetched_product.nome_produto == "Burger"

def test_get_products_by_tenant(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="multi_prod_tenant", nome_loja="Multi Prod Store", ia_personality="multi_prod_p", ai_prompt_description="multi_prod_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "multi_prod_config")
    product_crud.create_product(db_session, schemas.ProductCreate(nome_produto="Item A", preco_base=10.0), "multi_prod_tenant")
    product_crud.create_product(db_session, schemas.ProductCreate(nome_produto="Item B", preco_base=12.0), "multi_prod_tenant")
    
    products = product_crud.get_products_by_tenant(db_session, "multi_prod_tenant")
    assert len(products) == 2
    assert {p.nome_produto for p in products} == {"Item A", "Item B"}

def test_update_product(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="upd_prod_tenant", nome_loja="Upd Prod Store", ia_personality="upd_p", ai_prompt_description="upd_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "upd_prod_config")
    product_data = schemas.ProductCreate(nome_produto="Old Product", preco_base=10.0)
    created_product = product_crud.create_product(db_session, product_data, "upd_prod_tenant")
    
    update_data = schemas.ProductUpdate(nome_produto="Updated Product", preco_base=15.0)
    updated_product = product_crud.update_product(db_session, created_product.id_produto, update_data)
    
    assert updated_product.nome_produto == "Updated Product"
    assert updated_product.preco_base == 15.0

def test_delete_product(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="del_prod_tenant", nome_loja="Del Prod Store", ia_personality="del_p", ai_prompt_description="del_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "del_prod_config")
    product_data = schemas.ProductCreate(nome_produto="Product to Delete", preco_base=5.0)
    created_product = product_crud.create_product(db_session, product_data, "del_prod_tenant")
    
    product_crud.delete_product(db_session, created_product.id_produto)
    assert product_crud.get_product(db_session, created_product.id_produto) is None

def test_link_and_unlink_opcional_to_product(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="link_tenant", nome_loja="Link Store", ia_personality="link_p", ai_prompt_description="link_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "link_config")
    product_data = schemas.ProductCreate(nome_produto="Linked Product", preco_base=10.0)
    opcional_data = schemas.OpcionalCreate(nome_opcional="Linked Opcional", tipo_opcional="Adicional", preco_adicional=2.0)
    
    product = product_crud.create_product(db_session, product_data, "link_tenant")
    opcional = opcional_crud.create_opcional(db_session, opcional_data, "link_tenant")
    
    # Link
    product_crud.link_opcional_to_product(db_session, product.id_produto, opcional.id_opcional)
    linked_opcionais = product_crud.get_linked_opcionais(db_session, product.id_produto)
    assert len(linked_opcionais) == 1
    assert linked_opcionais[0].id_opcional == opcional.id_opcional

    # Unlink
    product_crud.unlink_opcional_from_product(db_session, product.id_produto, opcional.id_opcional)
    linked_opcionais = product_crud.get_linked_opcionais(db_session, product.id_produto)
    assert len(linked_opcionais) == 0

# Testes para Opcional CRUD
def test_create_opcional(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="opc_tenant", nome_loja="Opc Store", ia_personality="opc_p", ai_prompt_description="opc_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "opc_config")
    opcional_data = schemas.OpcionalCreate(nome_opcional="Molho Extra", tipo_opcional="Adicional", preco_adicional=2.5)
    
    opcional = opcional_crud.create_opcional(db_session, opcional_data, "opc_tenant")
    
    assert opcional.nome_opcional == "Molho Extra"
    assert opcional.tenant_id == "opc_tenant"

def test_get_opcional(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="get_opc_tenant", nome_loja="Get Opc Store", ia_personality="get_opc_p", ai_prompt_description="get_opc_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "get_opc_config")
    opcional_data = schemas.OpcionalCreate(nome_opcional="Cebola Crocante", preco_adicional=3.0, tipo_opcional="Adicional")
    created_opcional = opcional_crud.create_opcional(db_session, opcional_data, "get_opc_tenant")
    
    fetched_opcional = opcional_crud.get_opcional(db_session, created_opcional.id_opcional)
    assert fetched_opcional.nome_opcional == "Cebola Crocante"

def test_get_opcionais_by_tenant(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="multi_opc_tenant", nome_loja="Multi Opc Store", ia_personality="multi_opc_p", ai_prompt_description="multi_opc_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "multi_opc_config")
    opcional_crud.create_opcional(db_session, schemas.OpcionalCreate(nome_opcional="Opcional A", preco_adicional=1.0, tipo_opcional="Adicional"), "multi_opc_tenant")
    opcional_crud.create_opcional(db_session, schemas.OpcionalCreate(nome_opcional="Opcional B", preco_adicional=1.5, tipo_opcional="Adicional"), "multi_opc_tenant")
    
    opcionais = opcional_crud.get_opcionais_by_tenant(db_session, "multi_opc_tenant")
    assert len(opcionais) == 2
    assert {o.nome_opcional for o in opcionais} == {"Opcional A", "Opcional B"}

def test_update_opcional(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="upd_opc_tenant", nome_loja="Upd Opc Store", ia_personality="upd_p", ai_prompt_description="upd_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "upd_opc_config")
    opcional_data = schemas.OpcionalCreate(nome_opcional="Old Opcional", preco_adicional=1.0, tipo_opcional="Adicional")
    created_opcional = opcional_crud.create_opcional(db_session, opcional_data, "upd_opc_tenant")
    
    update_data = schemas.OpcionalUpdate(nome_opcional="Updated Opcional", preco_adicional=2.0, tipo_opcional="Adicional")
    updated_opcional = opcional_crud.update_opcional(db_session, created_opcional.id_opcional, update_data)
    
    assert updated_opcional.nome_opcional == "Updated Opcional"
    assert updated_opcional.preco_adicional == 2.0

def test_delete_opcional(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="del_opc_tenant", nome_loja="Del Opc Store", ia_personality="del_p", ai_prompt_description="del_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "del_opc_config")
    opcional_data = schemas.OpcionalCreate(nome_opcional="Opcional to Delete", preco_adicional=0.5, tipo_opcional="Adicional")
    created_opcional = opcional_crud.create_opcional(db_session, opcional_data, "del_opc_tenant")
    
    opcional_crud.delete_opcional(db_session, created_opcional.id_opcional)
    assert opcional_crud.get_opcional(db_session, created_opcional.id_opcional) is None

# Testes para Promocao CRUD
def test_create_promocao(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="promo_tenant", nome_loja="Promo Store", ia_personality="promo_p", ai_prompt_description="promo_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "promo_config")
    promocao_data = schemas.PromocaoCreate(nome_promocao="Desconto de Verão", descricao_para_ia="Promoção de verão", condicao_json={"tipo": "DIA_SEMANA", "dias": ["MON"]}, acao_json={"tipo": "DESCONTO_PERCENTUAL", "valor": 10.0}, is_ativa=True)
    
    promocao = promocao_crud.create_promocao(db_session, promocao_data, "promo_tenant")
    
    assert promocao.nome_promocao == "Desconto de Verão"
    assert promocao.tenant_id == "promo_tenant"
    assert promocao.is_ativa == True

def test_get_promocao(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="get_promo_tenant", nome_loja="Get Promo Store", ia_personality="get_promo_p", ai_prompt_description="get_promo_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "get_promo_config")
    promocao_data = schemas.PromocaoCreate(nome_promocao="Frete Grátis", descricao_para_ia="Frete grátis", condicao_json={"tipo": "VALOR_MINIMO", "valor": 50.0}, acao_json={"tipo": "FRETE_GRATIS"}, is_ativa=True)
    created_promocao = promocao_crud.create_promocao(db_session, promocao_data, "get_promo_tenant")
    
    fetched_promocao = promocao_crud.get_promocao(db_session, created_promocao.id_promocao)
    assert fetched_promocao.nome_promocao == "Frete Grátis"

def test_get_promocoes_by_tenant(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="multi_promo_tenant", nome_loja="Multi Promo Store", ia_personality="multi_promo_p", ai_prompt_description="multi_promo_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "multi_promo_config")
    promocao_crud.create_promocao(db_session, schemas.PromocaoCreate(nome_promocao="Promo A", is_ativa=True), "multi_promo_tenant")
    promocao_crud.create_promocao(db_session, schemas.PromocaoCreate(nome_promocao="Promo B", is_ativa=False), "multi_promo_tenant")
    
    promocoes = promocao_crud.get_promocoes_by_tenant(db_session, "multi_promo_tenant")
    assert len(promocoes) == 2
    assert {p.nome_promocao for p in promocoes} == {"Promo A", "Promo B"}

def test_update_promocao(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="upd_promo_tenant", nome_loja="Upd Promo Store", ia_personality="upd_p", ai_prompt_description="upd_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "upd_promo_config")
    promocao_data = schemas.PromocaoCreate(nome_promocao="Old Promo", is_ativa=True)
    created_promocao = promocao_crud.create_promocao(db_session, promocao_data, "upd_promo_tenant")
    
    update_data = schemas.PromocaoUpdate(nome_promocao="Updated Promo", is_ativa=False)
    updated_promocao = promocao_crud.update_promocao(db_session, created_promocao.id_promocao, update_data)
    
    assert updated_promocao.nome_promocao == "Updated Promo"
    assert updated_promocao.is_ativa == False

def test_delete_promocao(db_session: Session):
    tenant_crud.create_tenant(db_session, schemas.TenantCreate(tenant_id="del_promo_tenant", nome_loja="Del Promo Store", ia_personality="del_p", ai_prompt_description="del_desc", endereco="e", cep="c", latitude=0.0, longitude=0.0), "del_promo_config")
    promocao_data = schemas.PromocaoCreate(nome_promocao="Promo to Delete", is_ativa=True)
    created_promocao = promocao_crud.create_promocao(db_session, promocao_data, "del_promo_tenant")
    
    promocao_crud.delete_promocao(db_session, created_promocao.id_promocao)
    assert promocao_crud.get_promocao(db_session, created_promocao.id_promocao) is None

