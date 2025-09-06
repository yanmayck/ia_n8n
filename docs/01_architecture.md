# Arquitetura do Sistema: Projeto IA-N8N

## 1. Visão Geral

O `ia_n8n` é um sistema de inteligência artificial projetado para atuar como um **atendente de food service autônomo e de alta performance**. O objetivo é gerenciar conversas com clientes via WhatsApp, guiando-os de forma natural e eficiente através do processo completo de um pedido: desde a consulta do cardápio e anotação de itens customizados até o cálculo de frete e finalização da compra.

A filosofia central do projeto é a **confiabilidade e precisão**, alcançadas através de uma arquitetura de "equipe de IAs" (Agentes) especializados que operam dentro de um fluxo de trabalho (Workflow) determinístico.

## 2. Tecnologias Principais

- **Framework Web:** FastAPI
- **Banco de Dados Relacional:** PostgreSQL
- **ORM (Object-Relational Mapping):** SQLAlchemy
- **Gerenciamento de Migrações de DB:** Alembic
- **Banco de Dados Vetorial:** PGVector (para buscas semânticas)
- **Cache e Gerenciamento de Estado:** Redis
- **Biblioteca de Agentes de IA:** Agno
- **Validação de Dados:** Pydantic

## 3. Arquitetura e Fluxo de Trabalho (Workflow)

Para evitar os erros e a imprevisibilidade de uma única IA monolítica, o sistema quebra tarefas complexas em passos menores e especializados, gerenciados pelo `OrchestratorAgent` (`services/main_orchestrator.py`).

O fluxo principal consiste em 3 estágios:

1.  **Recepção e Análise de Intenção (`receptionist_agent`):**
    -   **Função:** Atua como o "ouvinte" da equipe.
    -   **Responsabilidade:** Analisar a mensagem do usuário e traduzi-la para uma tarefa estruturada (ex: `BuscaDeProduto`, `CalcularFrete`, `Saudacao`).

2.  **Roteamento e Execução de Tarefas (Orquestrador e Ferramentas):**
    -   **Função:** Com base na tarefa identificada, o orquestrador aciona o especialista ou a ferramenta correta.
    -   **Especialistas:**
        *   **Busca de Produtos:** Usa o `ProductService` para realizar buscas precisas e filtradas no banco de dados SQL.
        *   **Cálculo de Frete:** Usa a ferramenta `freight_calculator` que se integra com a API do Google Maps.
        *   **Perguntas Gerais:** Usa o `rag_search_step` para fazer uma busca semântica no banco de dados vetorial (PGVector) por informações institucionais da loja.

3.  **Formulação da Resposta (`response_formulation_agent`):**
    -   **Função:** Atua como o "porta-voz" da equipe.
    -   **Responsabilidade:** Pega os dados coletados pelos especialistas (resultados da busca, valor do frete, etc.) e os apresenta ao cliente de forma coesa, amigável e alinhada com a personalidade da loja.

## 4. Funcionalidades Chave e Como Funcionam

### Pesquisa de Produtos
-   **Fluxo:** `receptionist_agent` -> `main_orchestrator.py` -> `business_logic/product_service.py` -> `crud/product_crud.py` -> DB.
-   **Funcionamento:** A busca é feita no banco de dados SQL e suporta filtros por nome, categoria e ingredientes (incluir/excluir). Utiliza uma lógica de 3 níveis (correspondência exata, substring e similaridade) para máxima precisão.

### Venda Proativa (Upsell/Cross-sell)
-   **Fluxo:** Após um produto ser encontrado, o `suggestion_gathering_step` no orquestrador é ativado.
-   **Funcionamento:** Este passo obrigatoriamente chama as ferramentas `get_contextual_suggestions_tool` e `get_applicable_promotions_tool`. Os resultados (opcionais e promoções) são então passados para o `response_formulation_agent`, que tem a instrução de apresentá-los ao cliente.

### Cálculo de Frete
-   **Fluxo:** `receptionist_agent` -> `main_orchestrator.py` (ativa `geocode_step` e `freight_calculation_step`) -> `services/tools/geolocation.py` (`freight_calculator`).
-   **Funcionamento:** O processo é 100% determinístico.
    1.  O endereço em texto é convertido para coordenadas (via `geocode_address`).
    2.  A distância entre as coordenadas do cliente e da loja é calculada (via `google_maps_client`).
    3.  A regra de negócio de frete do `tenant` (taxa fixa ou por km) é aplicada ao resultado.
    4.  A IA apenas lê e apresenta o resultado final, ela não participa do cálculo.

## 5. Estrutura de Pastas

A organização do projeto segue uma arquitetura em camadas para separação de responsabilidades.

-   `ia_n8n/`
    -   `api/`: Camada de Interface da API (Endpoints FastAPI).
    -   `core/`: O núcleo do sistema, definindo as estruturas de dados (models, schemas, etc.).
    -   `crud/`: Camada de Acesso a Dados (Create, Read, Update, Delete).
    -   `docs/`: **(Novo)** Documentação centralizada do projeto.
    -   `services/`: Camada de Lógica de Negócio.
        -   `main_orchestrator.py`: O cérebro do sistema.
        -   `chat_handler.py`: Ponto de entrada que recebe as chamadas da API.
        -   `state_manager.py`: Gerencia o estado da conversa com Redis.
        -   `data_sync_service.py`: Gerencia a sincronização de dados com o VectorDB.
        -   `agents/`: Definições de cada agente especializado.
        -   `business_logic/`: Lógica de negócio principal (busca de produtos, promoções).
        -   `integrations/`: Clientes para APIs e serviços externos.
        -   `tools/`: Ferramentas que os agentes podem usar.
    -   `tests/`: Testes unitários e de integração.
    -   `templates/`: Interface web para o painel de administração.
