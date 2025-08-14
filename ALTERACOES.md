# Plano de Ação: Refatoração do Fluxo de Pesquisa e Venda (v2 - Detalhado)

Este documento detalha as alterações planejadas para o `ia_n8n` a fim de tornar o comportamento do agente de IA mais preciso, consistente e alinhado com a persona de um atendente de food service de alta performance.

## Objetivo Principal

Eliminar ambiguidades no fluxo de pesquisa de produtos e tornar o comportamento de venda proativa (upsell/cross-sell) uma regra de negócio determinística, garantindo uma experiência de usuário confiável e profissional.

## Pré-requisitos

- Antes de iniciar, é recomendado fazer um backup dos arquivos que serão modificados, principalmente:
  - `ia_n8n/services/product_service.py`
  - `ia_n8n/services/orchestrator_agent.py`
  - `ia_n8n/services/agents/response_formulation_agent.py`

---

## Fase 1: Centralizar e Fortalecer a Lógica de Busca [CONCLUÍDO]

**Meta:** Corrigir a falha da "Intenção Perdida", garantindo que os filtros de busca detalhados (ex: "sem cebola") sejam sempre aplicados.

### 1.1. Aprimorar `ProductService`

*   **Arquivo:** `ia_n8n/services/product_service.py`
*   **Ação:** Modificar a função `find_product` para que ela aceite um objeto `BuscaDeProduto` (de `core/schemas.py`) em vez de uma simples string.
*   **Detalhes da Implementação:**
    A assinatura da função mudará:
    ```python
    # ANTES:
    def find_product(self, query: str, similarity_threshold: int = 80) -> Optional[models.Product]:
        ...

    # DEPOIS:
    from core.schemas import BuscaDeProduto
    def find_product_filtered(self, search_criteria: BuscaDeProduto, similarity_threshold: int = 80) -> List[models.Product]:
        ...
    ```
    A lógica interna será reescrita para construir uma query SQLAlchemy dinâmica:
    ```python
    # Exemplo da nova lógica dentro de find_product_filtered
    
    # 1. Query base
    query = self.db.query(models.Product).filter(models.Product.tenant_id == self.tenant_id)

    # 2. Aplicar filtros de categoria, se existirem
    if search_criteria.categorias:
        query = query.filter(models.Product.categoria_produto.in_(search_criteria.categorias))

    # 3. Aplicar filtros de exclusão de ingredientes, se existirem
    if search_criteria.ingredientes_excluir:
        for ingrediente in search_criteria.ingredientes_excluir:
            query = query.filter(models.Product.descricao_produto.not_ilike(f'''%{ingrediente}%'''))
    
    # 4. Aplicar busca por nome (dos termos gerais)
    if search_criteria.termos_gerais:
        # Lógica de busca por nome (exata, substring, fuzzy) nos resultados já filtrados
        ...

    return query.all()
    ```

### 1.2. Atualizar o Orquestrador

*   **Arquivo:** `ia_n8n/services/orchestrator_agent.py`
*   **Ação:** Na função `_handle_product_search_executor`, passar o objeto `BuscaDeProduto` completo para a nova função `product_service.find_product_filtered`.
*   **Detalhes da Implementação:**
    ```python
    # ANTES:
    # query = " ".join(receptionist_output.termos_gerais)
    # found_product = await run_in_threadpool(product_service.find_product, query=query)

    # DEPOIS:
    receptionist_output = step_input.additional_data.get('receptionist_output')
    found_products = await run_in_threadpool(product_service.find_product_filtered, search_criteria=receptionist_output)
    step_input.additional_data["search_results"] = found_products
    ```

---

## Fase 2: Unificar as Rotas de Pesquisa [CONCLUÍDO]

**Meta:** Corrigir a "Rota Dupla", eliminando a inconsistência entre a busca SQL e a busca Vetorial para produtos.

### 2.1. Simplificar o Roteador

*   **Arquivo:** `ia_n8n/services/orchestrator_agent.py`
*   **Ação:** Alterar a lógica da função `_route_to_data_collection_step`.
*   **Detalhes da Implementação:** A lógica será ajustada para que qualquer intenção que pareça ser sobre produtos seja direcionada ao `product_search_step`.
    ```python
    # Lógica de roteamento a ser implementada
    
    receptionist_output = step_input.additional_data.get('receptionist_output')

    # Se a intenção já é uma busca de produto, a rota é clara.
    if isinstance(receptionist_output, BuscaDeProduto):
        return self.product_search_step

    # Se for uma pergunta geral, mas contém palavras-chave de comida, também direcionar para a busca.
    if isinstance(receptionist_output, AnaliseDeIntencao) and receptionist_output.tarefas:
        task_type = receptionist_output.tarefas[0].tipo_tarefa
        details = receptionist_output.tarefas[0].detalhes or ""
        
        # Palavras-chave que indicam uma pergunta sobre produto
        product_keywords = ['produto', 'cardápio', 'menu', 'comida', 'bebida', 'preço', 'tem']

        if any(keyword in details.lower() for keyword in product_keywords):
             return self.product_search_step # Rota unificada

        # Mapeamento para outras tarefas...
        task_map = { ... } 
        return task_map.get(task_type, self.rag_search_step) # RAG como fallback
    
    return self.rag_search_step
    ```

---

## Fase 3: Sistematizar o Comportamento de Vendedor [CONCLUÍDO]

**Meta:** Corrigir o "Vendedor Inconsistente", tornando a oferta de adicionais e promoções uma parte obrigatória e consistente do fluxo.

### 3.1. Adicionar Novo Passo ao Workflow

*   **Arquivo:** `ia_n8n/services/orchestrator_agent.py`
*   **Ação:** Inserir um novo `Step` no `Workflow` chamado `suggestion_gathering_step`.
*   **Detalhes da Implementação:** O workflow será redefinido para incluir o novo passo na sequência correta.
    ```python
    # Exemplo da nova definição do Workflow
    self.workflow = Workflow(
        name="Chatbot Workflow",
        steps=[
            self.receptionist_step,
            self.main_router, # Roteador que escolhe entre product_search, freight_calc, etc.
            self.suggestion_gathering_step, # <<< NOVO PASSO AQUI
            self.response_formulation_step,
        ]
    )
    ```
    Será criada a função executora `_suggestion_gathering_executor`, que chamará as ferramentas de sugestão e promoção e passará os resultados adiante via `additional_data`.

### 3.2. Forçar a Apresentação das Sugestões

*   **Arquivo:** `ia_n8n/services/agents/response_formulation_agent.py`
*   **Ação:** Adicionar uma instrução explícita e de alta prioridade ao prompt do agente.
*   **Detalhes da Implementação:** O array `instructions` do agente será modificado para incluir:
    ```python
    instructions=[
        "### REGRAS DE OURO ###",
        "1. **Priorize o Contexto:** ...",
        "2. **Apresente Ofertas (REGRA INVIOLÁVEL):** Se o contexto contiver uma lista de 'sugestoes' ou 'promocoes', após confirmar o item do cliente, você DEVE OBRIGATORIAMENTE apresentar essas opções de forma natural e convidativa. Exemplo: 'Ok, anotei seu X-Bacon. Ele fica ótimo com nossa porção de fritas. Deseja incluir?'.",
        # ... outras instruções
    ]
    ```

---

## Impacto e Benefícios Esperados

*   **Precisão:** As buscas de produtos respeitarão 100% das customizações do cliente (ex: "sem glúten", "sem cebola").
*   **Consistência:** Todas as perguntas sobre produtos seguirão o mesmo fluxo lógico, resultando em uma experiência de usuário previsível e confiável.
*   **Proatividade de Vendas:** A oferta de itens adicionais e promoções se tornará uma regra de negócio, aumentando o potencial de valor por pedido e melhorando o serviço.
*   **Clareza Arquitetural:** A função de cada componente se torna mais clara, facilitando a manutenção e futuras expansões do sistema.