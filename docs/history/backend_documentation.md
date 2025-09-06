# Documentação Técnica do Backend - IA-N8N

Esta documentação fornece uma visão geral técnica da arquitetura, tecnologias e convenções usadas no backend do projeto IA-N8N.

## 1. Tecnologias Principais

- **Framework:** FastAPI
- **Banco de Dados Relacional:** PostgreSQL (via Supabase)
- **ORM:** SQLAlchemy com Alembic para migrações
- **Banco de Dados Vetorial:** PGVector
- **Banco de Dados de Cache/Estado:** Redis
- **Biblioteca de Agentes de IA:** Agno
- **Validação de Dados:** Pydantic

## 2. Estrutura de Pastas

A estrutura do projeto é organizada por camadas de responsabilidade:

- `ia_n8n/`
    - `api/`: Define os endpoints da API REST usando FastAPI.
    - `core/`: Contém o núcleo do sistema, como modelos de dados (`models.py`), schemas de validação (`schemas.py`) e configuração de banco de dados.
    - `crud/`: Funções para operações diretas no banco de dados (Create, Read, Update, Delete).
    - `services/`: A camada de serviço que contém a lógica de negócio e orquestração.
        - `main_orchestrator.py`: O cérebro do sistema, que gerencia o workflow da conversa.
        - `chat_handler.py`: O ponto de entrada que conecta a API à lógica de orquestração.
        - `agents/`: Definições dos agentes de IA especializados.
        - `business_logic/`: Lógica de negócio específica, como busca de produtos e regras de promoção.
        - `integrations/`: Clientes para se comunicar com APIs externas (Google Maps, Supabase, etc.).
        - `tools/`: Ferramentas que os agentes podem executar.
    - `tests/`: Testes unitários e de integração.

## 3. Setup e Instalação

1.  **Clone o repositório.**
2.  **Crie e ative um ambiente virtual Python:** `python -m venv venv` e `source venv/bin/activate` (ou `venv\Scripts\activate` no Windows).
3.  **Instale as dependências:** `pip install -r requirements.txt`.
4.  **Configure as variáveis de ambiente:** Copie `.env.example` para `.env` e preencha as chaves de API e URLs do banco de dados.
5.  **Execute as migrações do banco de dados:** `alembic upgrade head`.

## 4. Executando a Aplicação

- **Para desenvolvimento:**
  ```bash
  uvicorn api.main:app --reload
  ```
- **Para testes:**
  ```bash
  pytest
  ```

## 5. Arquitetura e Conceitos Chave

- **Fluxo Determinístico:** A lógica crítica (cálculo de frete, aplicação de regras) é executada em código Python puro para garantir previsibilidade e precisão. A IA é usada para compreensão de linguagem e formulação de respostas, não para cálculos.
- **Equipe de Agentes:** O sistema utiliza múltiplos agentes especializados (recepcionista, anotador de pedidos, etc.), orquestrados pelo `main_orchestrator.py`, para dividir tarefas complexas em passos menores e mais confiáveis.
- **Memória em Duas Camadas:**
    1.  **Memória de Fatos (Ativa):** Gerenciada pela biblioteca `Agno` (`PostgresMemoryDb`), armazena fatos estruturados sobre o usuário (ex: endereço, último pedido) na tabela `user_memories` para recuperação rápida.
    2.  **Memória Conversacional (Inativa):** A infraestrutura para um arquivo completo de conversas existe em `services/agents/base_agent.py` (usando `VectorDBManager`), mas atualmente não está sendo chamada pelo fluxo principal.
