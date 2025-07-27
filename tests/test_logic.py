import pytest
from sqlalchemy.orm import Session
from services.rules_engine import RulesEngine
from crud import product_crud, opcional_crud, promocao_crud, tenant_crud # Import tenant_crud
from core import schemas

def test_get_contextual_suggestions(db_session: Session):
    # 1. Criar dados de teste
    tenant_id = "logic_test_tenant"
    # Criar o tenant primeiro para satisfazer a chave estrangeira
    tenant_data = schemas.TenantCreate(
        tenant_id=tenant_id,
        nome_loja="Loja de Teste Lógico",
        ia_personality="personalidade_logica",
        ai_prompt_description="Prompt para teste de lógica",
        endereco="Rua da Lógica, 101",
        cep="10101-101",
        latitude=0.0,
        longitude=0.0
    )
    tenant_crud.create_tenant(db_session, tenant_data, "Config AI de teste")

    product_data = schemas.ProductCreate(nome_produto="Hamburguer Teste", preco_base=15.0)
    db_product = product_crud.create_product(db_session, product_data, tenant_id)
    
    opcional_data1 = schemas.OpcionalCreate(nome_opcional="Bacon Extra", tipo_opcional="Adicional", preco_adicional=3.0)
    db_opcional1 = opcional_crud.create_opcional(db_session, opcional_data1, tenant_id)
    
    opcional_data2 = schemas.OpcionalCreate(nome_opcional="Queijo Extra", tipo_opcional="Adicional", preco_adicional=2.5)
    db_opcional2 = opcional_crud.create_opcional(db_session, opcional_data2, tenant_id)

    # 2. Ligar opcionais ao produto
    product_crud.link_opcional_to_product(db_session, db_product.id_produto, db_opcional1.id_opcional)
    product_crud.link_opcional_to_product(db_session, db_product.id_produto, db_opcional2.id_opcional)

    # 3. Executar a lógica e verificar
    rules_engine = RulesEngine(db_session)
    suggestions = rules_engine.get_contextual_suggestions(db_product.id_produto)

    assert len(suggestions) == 2
    suggestion_names = {s['nome'] for s in suggestions}
    assert "Bacon Extra" in suggestion_names
    assert "Queijo Extra" in suggestion_names

# Adicione mais testes para a lógica de promoções e o orchestrator aqui...
