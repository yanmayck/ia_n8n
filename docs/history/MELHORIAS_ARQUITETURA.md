# Plano de Melhorias de Arquitetura e Sincronização (Revisado)

Este documento detalha as melhorias arquiteturais planejadas para os projetos `ia_n8n` e `business-whats-dashboard`. O objetivo é tornar a plataforma mais robusta, automatizada e fácil de manter.

## Prioridade 1: Sincronização Automática e Desacoplamento

Estas duas melhorias serão implementadas em conjunto, pois uma depende da outra.

### A. Implementação de Webhook para Sincronização Automática

-   **Problema Atual:** A sincronização de dados do `business-whats-dashboard` para o `ia_n8n` depende de um gatilho manual e está incompleta.
-   **Solução Proposta:** Implementar um sistema de **webhook**. Toda vez que um tenant for criado ou atualizado na interface de comandas, o backend do dashboard irá notificar o `ia_n8n` em tempo real, enviando um pacote completo com todos os dados atualizados do tenant.
-   **Benefícios:**
    -   Sincronização 100% automática e em tempo real.
    -   Elimina a necessidade de intervenção manual.
    -   Garante que a IA sempre opere com os dados mais recentes.

### B. Desacoplamento de Tenant ID e Instância do WhatsApp

-   **Problema Atual:** O `ia_n8n` atualmente exige que o `tenant_id` interno seja idêntico ao "Nome da Instância" da Evolution API, o que é rígido e propenso a erros.
-   **Análise Corrigida:** O `business-whats-dashboard` já possui uma tabela (`whatsapp_instances`) que associa um `tenant_id` a um `instance_name`, resolvendo parte do problema. A pendência está no `ia_n8n`.
-   **Solução Proposta:**
    1.  **No `ia_n8n`:** Adicionar uma nova coluna `evolution_instance_name` na tabela `tenants`.
    2.  **No `ia_n8n`:** Alterar a rota de validação (`POST /tenants/config`) para buscar o tenant pelo novo campo `evolution_instance_name`, em vez de pelo `tenant_id`.
    3.  **No Webhook:** O pacote de dados enviado pelo `business-whats-dashboard` irá incluir o `instance_name`, que o `ia_n8n` usará para criar ou atualizar o registro correto.
-   **Benefícios:**
    -   **Flexibilidade:** Permite que os nomes das instâncias e os IDs dos tenants sejam diferentes.
    -   **Robustez:** Reduz drasticamente a chance de erros de configuração manual.
    -   **Segurança:** Evita a exposição de IDs internos do sistema.

## Melhoria Futura (Pós-MVP)

### Simplificação do Gerenciamento de Chaves de API

-   **Problema:** A interface permite cadastrar chaves de API para Google Maps e Evolution que não são utilizadas pelo `ia_n8n` no modelo por-tenant.
-   **Solução:** Em uma fase futura, a interface no `business-whats-dashboard` será simplificada para gerenciar apenas a chave de API do Gemini por tenant, incluindo o campo de **Prioridade** para o sistema de failover.