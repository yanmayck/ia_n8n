# Guia de Instalação e Configuração

Este guia detalha todos os passos necessários para configurar e executar o projeto `ia_n8n` em um ambiente de desenvolvimento local.

## 1. Pré-requisitos

Antes de começar, garanta que você tenha os seguintes softwares instalados na sua máquina:

-   **Git:** Para clonar o repositório.
-   **Python:** Versão 3.10 ou superior.
-   **Docker e Docker Compose:** Para executar os serviços de banco de dados (PostgreSQL) e cache (Redis) de forma isolada.

## 2. Passo a Passo da Instalação

### Passo 1: Clonar o Repositório

Abra seu terminal e clone o projeto para a sua máquina local:

```bash
git clone <URL_DO_REPOSITORIO>
cd ia_n8n
```

### Passo 2: Criar e Ativar o Ambiente Virtual

É uma boa prática usar um ambiente virtual para isolar as dependências do projeto.

```bash
# Criar o ambiente virtual
python -m venv venv

# Ativar no Windows
.\venv\Scripts\activate

# Ativar no macOS/Linux
source venv/bin/activate
```

### Passo 3: Instalar as Dependências

Com o ambiente virtual ativado, instale todas as bibliotecas Python necessárias com um único comando:

```bash
pip install -r requirements.txt
```

### Passo 4: Configurar Variáveis de Ambiente

As configurações sensíveis e específicas do ambiente são gerenciadas através de um arquivo `.env`.

1.  **Copie o arquivo de exemplo:**

    ```bash
    # No Windows
    copy .env.example .env

    # No macOS/Linux
    cp .env.example .env
    ```

2.  **Edite o arquivo `.env`:** Abra o arquivo `.env` recém-criado em um editor de texto e preencha as variáveis. Para desenvolvimento local, as configurações mais importantes são:

    -   `DATABASE_URL`: **Mantenha o valor padrão do `.env.example`** para conectar ao banco de dados do Docker que será iniciado no próximo passo (`postgresql://testuser:testpassword@localhost:5435/testdb`).
    -   `REDIS_HOST`: **Mantenha como `localhost`**.
    -   `REDIS_PORT`: **Mantenha como `6380`**.
    -   `GEMINI_API_KEY`: Insira sua chave de API do Google Gemini.
    -   `GOOGLE_MAPS_API_KEY`: Insira sua chave da API do Google Maps (essencial para o cálculo de frete).
    -   `SECRET_KEY`: Pode manter a chave de exemplo para desenvolvimento, mas gere uma nova para produção.
    -   `ADMIN_PASSWORD`: Defina uma senha para acessar o painel de administração.

### Passo 5: Iniciar os Serviços (Banco de Dados e Redis)

Usamos o Docker Compose para iniciar um contêiner PostgreSQL (com a extensão PGVector) e um contêiner Redis. O arquivo `docker-compose.test.yml` é configurado para este fim.

```bash
docker-compose -f docker-compose.test.yml up -d
```

-   O comando `-d` executa os contêineres em modo "detached" (em segundo plano).
-   Para parar os serviços, use `docker-compose -f docker-compose.test.yml down`.

### Passo 6: Aplicar as Migrações do Banco de Dados

Com o banco de dados rodando no Docker, precisamos criar as tabelas. Usamos o Alembic para gerenciar as migrações do schema do banco.

Execute o seguinte comando para aplicar todas as migrações:

```bash
alembic upgrade head
```

Isso criará todas as tabelas necessárias no seu banco de dados de teste.

### Passo 7: Executar a Aplicação

Finalmente, inicie o servidor da API FastAPI com o Uvicorn.

```bash
uvicorn api.main:app --reload
```

-   A flag `--reload` faz com que o servidor reinicie automaticamente sempre que você salvar uma alteração no código.
-   A API estará acessível em `http://localhost:8000`.
-   O painel de administração estará na mesma URL: `http://localhost:8000`.

## 3. Executando os Testes (Opcional)

Para garantir que tudo está funcionando corretamente, você pode executar a suíte de testes automatizados:

```bash
pytest
```
