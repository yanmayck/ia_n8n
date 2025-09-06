# Referência da API

Esta seção documenta os principais endpoints da API REST do `ia_n8n`. A maioria das rotas de gerenciamento requer autenticação via token JWT.

## Autenticação

`Arquivo: api/routers/authentication.py`

-   **`POST /login`**
    -   **Descrição:** Autentica um administrador usando a senha definida na variável de ambiente `ADMIN_PASSWORD`.
    -   **Corpo da Requisição:** `FormData` com o campo `password`.
    -   **Resposta de Sucesso:** Retorna um `access_token` JWT.

## Interação com a IA

`Arquivo: api/routers/ai.py`

-   **`POST /ai`**
    -   **Descrição:** Principal ponto de entrada para conversas. Recebe a mensagem do usuário e outros dados, e retorna a resposta da IA após processá-la no workflow.
    -   **Corpo da Requisição:** `schemas.AIWebhookRequest`.
    -   **Resposta de Sucesso:** Uma lista de `schemas.AIWebhookResponsePart`.

-   **`POST /calcular-frete`**
    -   **Descrição:** Calcula o frete entre a loja e o cliente. **Requer autenticação.**
    -   **Corpo da Requisição:** JSON com `tenant_id`, `cliente_lat`, `cliente_lng`.
    -   **Resposta de Sucesso:** Detalhes da distância e custo (se aplicável).

## Gerenciamento de Tenants (Lojas)

`Arquivo: api/routers/tenants.py`

*Todas as rotas abaixo requerem autenticação.*

-   **`POST /tenants/`**: Cria um novo tenant (loja) com todos os seus dados, incluindo o upload de arquivos.
-   **`GET /tenants/`**: Lista todos os tenants cadastrados.
-   **`GET /tenants/{tenant_id}`**: Obtém os detalhes de um tenant específico.
-   **`PUT /tenants/{tenant_id}`**: Atualiza os dados de um tenant.
-   **`DELETE /tenants/{tenant_id}`**: Remove um tenant e todos os seus dados associados.
-   **`PUT /tenants/{tenant_id}/toggle-status`**: Ativa ou desativa um tenant.
-   **`POST /tenants/config`**: Rota interna para o sistema buscar a configuração de um tenant usando o `evolution_instance_name`.
-   **`GET /tenants/{tenant_id}/loja_txt`**: Retorna o conteúdo do arquivo de texto de informações da loja.
-   **`POST /tenants/{tenant_id}/sync-menu`**: Dispara a sincronização do cardápio com a plataforma de gestão externa.
-   **`POST /tenants/{tenant_id}/menu-images/`**: Faz upload de imagens de cardápio para o tenant.

## Sincronização (Webhook)

`Arquivo: api/routers/sync.py`

-   **`POST /sync/webhook`**
    -   **Descrição:** Endpoint seguro para receber um pacote completo de dados do `business-whats-dashboard` e sincronizar todas as informações do tenant (dados, produtos, chaves, etc.).
    -   **Autenticação:** Requer um segredo compartilhado no header `X-Sync-Secret`.

## Gerenciamento do Cardápio

As rotas de gerenciamento de `Produtos`, `Opcionais` e `Promoções` seguem o padrão RESTful e estão associadas a um `tenant_id`.

`Arquivos: products.py, opcionais.py, promocoes.py`

-   **`POST /<recurso>/{tenant_id}`**: Cria um novo item (produto, opcional, promoção).
-   **`GET /<recurso>/{tenant_id}`**: Lista todos os itens de um tenant.
-   **`PUT /<recurso>/{tenant_id}/{item_id}`**: Atualiza um item específico.
-   **`DELETE /<recurso>/{tenant_id}/{item_id}`**: Deleta um item específico.

### Associações

-   **`POST /products/{tenant_id}/{product_id}/opcionais/{opcional_id}`**: Associa um opcional a um produto.
-   **`DELETE /products/{tenant_id}/{product_id}/opcionais/{opcional_id}`**: Desassocia um opcional de um produto.
-   (A mesma lógica se aplica para associar promoções a produtos).

## Gerenciamento de Chaves de API e Personalidades

`Arquivos: api_keys.py, personalities.py`

-   As rotas seguem o mesmo padrão RESTful para criar, ler, atualizar e deletar chaves de API (por tenant) e personalidades (globais).
