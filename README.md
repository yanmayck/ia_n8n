# Sistema de Gerenciamento de Clientes com IA

## 🚀 Funcionalidades

### **Cadastro Completo de Clientes**
- **Nome da Instância**: Identificador único para buscar dados
- **Nome da Loja**: Nome para identificação visual
- **Personalidade da IA**: Como a IA vai agir
- **Endereço, CEP, Latitude, Longitude**: Localização da loja
- **Arquivo .txt**: Descrição completa da empresa
- **Arquivo Excel**: Tabela de produtos da loja

### **Gerenciamento**
- ✅ Listar todos os clientes
- ✅ Editar clientes (inline)
- ✅ Ativar/Desativar clientes
- ✅ Remover clientes
- ✅ Cálculo de frete via Google Maps

### **APIs Integradas**
- Google Maps API (cálculo de frete)
- Evolution API (WhatsApp)
- Gemini API (IA)

## 📁 Estrutura de Pastas

```
ia_n8n/
├── api/                 # Contém o arquivo principal da API (main.py)
│   └── main.py
├── core/                # Modelos de dados, schemas e configuração do banco
│   ├── database.py
│   ├── models.py
│   └── schemas.py
├── crud/                # Funções de operações de banco de dados (CRUD)
│   └── crud.py
├── services/            # Lógica de negócio, integração com IAs e APIs externas
│   └── services.py
├── templates/           # Arquivos HTML do frontend
│   └── index.html
├── logs/                # Arquivos de log da aplicação
├── .git/
├── venv/
├── requirements.txt
├── env_example.txt
├── README.md
└── .gitignore
```

## ⚙️ Configuração

### 1. **Instalar Dependências**
```bash
pip install -r requirements.txt
```

### 2. **Configurar Variáveis de Ambiente**
Crie um arquivo `.env` baseado no `env_example.txt`:

```env
# Configurações do Banco de Dados
DATABASE_URL=sqlite:///./database/chat_app.db

# APIs Externas
GOOGLE_MAPS_API_KEY=sua_google_maps_api_key_aqui
EVOLUTION_API_KEY=sua_evolution_api_key_aqui
GEMINI_API_KEY=sua_gemini_api_key_aqui

# Outras configurações
DEBUG=True
```

### 3. **Estrutura do Excel de Produtos**
O arquivo Excel deve ter as colunas:
- `name`: Nome do produto
- `price`: Preço do produto
- `retrieval_key`: Chave de busca (opcional)

## 🎯 Endpoints da API

### **Cadastro via Interface Web**
```
POST /tenants/
```
- Recebe: Formulário multipart com todos os dados + arquivos
- Cria: Tenant + Produtos do Excel

### **Cadastro via JSON (Primeira Requisição)**
```
POST /tenant-instancia/
```
- Recebe: JSON com chave "instancia"
- Exemplo:
```json
{
  "instancia": "loja_abc",
  "url": "https://api.loja.com",
  "is_active": true,
  "id_pronpt": "personalidade_vendedor"
}
```

### **Outros Endpoints**
- `GET /tenants/` - Listar clientes
- `GET /tenants/{id}` - Buscar cliente
- `PUT /tenants/{id}` - Atualizar cliente
- `PUT /tenants/{id}/toggle-status` - Ativar/Desativar
- `DELETE /tenants/{id}` - Remover cliente
- `POST /tenant-data/` - Buscar dados de tenant por instância
- `POST /ai` - Rota principal da IA (recebe mensagens e retorna respostas)
- `POST /personalities/` - Criar personalidade da IA
- `GET /get-file/{retrieval_key}` - Recuperar arquivos
- `POST /upload-products` - Upload de produtos via Excel
- `GET /products/{tenant_id}` - Buscar produtos por tenant
- `POST /calcular-frete` - Calcular frete

## 🚀 Como Usar

### 1. **Iniciar o Servidor**
Navegue até a pasta `ia_n8n` e execute:
```bash
uvicorn api.main:app --reload
```

### 2. **Acessar Interface Web**
- URL: http://localhost:8000
- Cadastre clientes com todos os dados
- Teste o cálculo de frete

### 3. **Cadastro via JSON**
Navegue até a pasta `ia_n8n` e execute:
```bash
curl -X POST "http://localhost:8000/tenant-instancia/" \
  -H "Content-Type: application/json" \
  -d '{
    "instancia": "minha_loja",
    "url": "https://api.minhaloja.com",
    "is_active": true,
    "id_pronpt": "vendedor_simpatico"
  }'
```

## 📊 Banco de Dados

O banco é criado automaticamente na pasta `database/` com as tabelas:
- `tenants`: Clientes/Lojas
- `personalities`: Personalidades da IA
- `products`: Produtos das lojas
- `interactions`: Interações com clientes

## 🔧 Desenvolvimento

### **Estrutura do Código**
- **Backend**: FastAPI + SQLAlchemy
- **Frontend**: HTML + JavaScript vanilla
- **Banco**: SQLite (pasta `ia_n8n/database/`)
- **APIs**: Google Maps, Evolution, Gemini
- **Logging**: Logs armazenados em `ia_n8n/logs/`

### **Fluxo de Dados**
1. **Primeira requisição (`/tenant-instancia/`)**: JSON com "instancia" → Cria tenant básico
2. **Cadastro completo (`/tenants/`)**: Interface web → Dados completos + arquivos
3. **Gerenciamento**: Interface web → CRUD completo via `api/main.py`
4. **Cálculo de frete**: Coordenadas → Google Maps API
5. **Interação com IA (`/ai`)**: Processa mensagem, salva interação, retorna resposta formatada.

## 🎉 Pronto para Uso!

O sistema está completo e pronto para cadastrar clientes, gerenciar dados e calcular fretes! 