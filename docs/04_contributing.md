# Guia para Desenvolvedores

Este documento estabelece as convenções, princípios e diretrizes para o desenvolvimento de novas funcionalidades ou para a manutenção do código do projeto `ia_n8n`.

## 1. Princípios Fundamentais de Arquitetura

-   **Separação de Responsabilidades:** Cada camada da aplicação (API, Serviços, CRUD) possui um propósito claro e bem definido. Mantenha a lógica de cada camada em seu respectivo diretório.

-   **Código Determinístico:** A lógica de negócio crítica, como cálculos de frete, aplicação de promoções e validações de pedido, **deve** ser implementada em código Python puro. A Inteligência Artificial é utilizada para tarefas de compreensão de linguagem e formulação de respostas, não para tomar decisões lógicas ou matemáticas.

-   **Comunicação Estruturada:** Use os schemas Pydantic (definidos em `core/schemas.py`) para validar todos os dados que fluem entre as camadas do sistema. Isso garante a integridade e a previsibilidade dos dados.

-   **Injeção de Dependência:** Utilize o sistema de injeção de dependência do FastAPI (ex: `Depends(get_db)`) para gerenciar recursos como sessões de banco de dados.

## 2. Convenções de Código

### Modularidade (Regra Principal)

A convenção mais importante a ser seguida é a da **máxima modularidade**. Sempre que possível, cada nova funcionalidade ou componente deve seguir o modelo de **uma função (ou classe) principal por arquivo**.

-   **Por quê?** Isso promove a máxima coesão (o código no arquivo tem um único propósito) e o mínimo acoplamento (o arquivo tem poucas dependências externas). O resultado é um código mais fácil de testar, manter e depurar.

-   **Exemplo Prático:** Em vez de ter um único arquivo `services/tools.py` com dezenas de ferramentas, o projeto possui uma pasta `services/tools/` onde cada arquivo (`geolocation.py`, `product.py`) define uma ou um pequeno grupo de ferramentas relacionadas.

### Estilo e Formatação

O projeto utiliza `black` e `ruff` para formatação e linting. Antes de submeter o código, é recomendado executar essas ferramentas para manter a consistência do estilo.

## 3. Fluxo de Trabalho para Novas Funcionalidades

O foco principal do desenvolvimento é criar e estabilizar o Produto Mínimo Viável (MVP).

-   **Consulte o Roadmap:** Antes de iniciar o desenvolvimento de uma nova funcionalidade, consulte o arquivo `docs/05_roadmap.md`.
-   **Evite Reimplementação:** Se uma ideia já estiver listada lá, ela pode ser considerada pós-MVP e não deve ser implementada no momento. Além disso, analise o código existente para verificar se uma funcionalidade similar (mesmo que inativa) já não foi criada.

## 4. Testes

-   É crucial adicionar testes unitários e de integração para qualquer nova lógica de negócio.
-   Os testes estão localizados na pasta `tests/`.
-   Para executar todos os testes, utilize o comando:

    ```bash
    pytest
    ```
