# Projeto IA-N8N: Atendente de Food Service com IA

O `ia_n8n` é um sistema de inteligência artificial avançado projetado para atuar como um **atendente de food service autônomo e de alta performance**. O objetivo é gerenciar conversas com clientes via WhatsApp, guiando-os de forma natural e eficiente através do processo completo de um pedido.

---

## 📚 Documentação Completa

Para uma visão aprofundada do projeto, consulte nossa documentação detalhada na pasta `docs/`:

-   **[Arquitetura do Sistema](./docs/01_architecture.md):** Entenda como o sistema funciona, seu fluxo de trabalho e os componentes.
-   **[Guia de Instalação e Configuração](./docs/02_setup.md):** Siga o passo a passo para configurar o ambiente de desenvolvimento.
-   **[Referência da API](./docs/03_api_reference.md):** Consulte a documentação de todos os endpoints da API.
-   **[Guia para Desenvolvedores](./docs/04_contributing.md):** Conheça as convenções e os padrões para contribuir com o projeto.
-   **[Roadmap de Desenvolvimento](./docs/05_roadmap.md):** Veja os planos e as futuras funcionalidades.

---

## 🚀 Quick Start (Desenvolvimento)

Siga os passos abaixo para executar o projeto localmente.

### 1. Pré-requisitos

-   Git
-   Python 3.10+
-   Docker e Docker Compose

### 2. Instalação

```bash
# 1. Clone o repositório
git clone <URL_DO_REPOSITORIO>
cd ia_n8n

# 2. Crie e ative um ambiente virtual
python -m venv venv
# No Windows: .\venv\Scripts\activate
# No macOS/Linux: source venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
# Copie o exemplo e edite o arquivo .env com suas chaves e senhas
cp .env.example .env

# 5. Inicie o banco de dados e o Redis com Docker
docker-compose -f docker-compose.test.yml up -d

# 6. Aplique as migrações do banco de dados
alembic upgrade head

# 7. Inicie o servidor da API
uvicorn api.main:app --reload
```

Após esses passos, a API estará rodando em `http://localhost:8000`.

## 📁 Estrutura de Pastas Principal

```
ia_n8n/
├── docs/                # Documentação detalhada do projeto
├── api/                 # Endpoints da API (FastAPI)
├── core/                # Modelos de dados, schemas e configuração do DB
├── crud/                # Funções de acesso ao banco de dados (CRUD)
├── services/            # Lógica de negócio, orquestração e agentes de IA
├── tests/               # Testes automatizados
├── templates/           # Arquivos HTML/JS/CSS para o painel de admin
├── alembic/             # Scripts de migração do banco de dados
├── requirements.txt     # Dependências do projeto
└── README.md            # Este arquivo
```

---

## 🏛️ Histórico de Desenvolvimento

Os documentos originais de planejamento e arquitetura que guiaram as fases iniciais do projeto foram arquivados para referência histórica. Eles podem ser encontrados na pasta [`docs/history/`](./docs/history/).
