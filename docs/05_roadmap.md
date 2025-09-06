# Roadmap de Desenvolvimento

Este documento centraliza as melhorias planejadas e as funcionalidades futuras para o projeto, consolidando as informações de vários documentos de planejamento (`melhorias.md`, `MELHORIAS_ARQUITETURA.md`, etc.).

## 1. Melhorias Prioritárias

Estas são as melhorias de arquitetura e funcionalidade que estão em foco para implementação a curto prazo.

### Sincronização Automática e Desacoplamento

-   **Problema:** A sincronização de dados do painel de controle (`business-whats-dashboard`) para a IA (`ia_n8n`) é manual e frágil.
-   **Solução Proposta:**
    1.  **Implementar Webhooks:** O painel de controle irá notificar o `ia_n8n` em tempo real via webhook sempre que um `tenant` for criado ou atualizado, enviando um pacote completo de dados.
    2.  **Desacoplar IDs:** O `ia_n8n` será modificado para associar um `tenant` ao `evolution_instance_name` (nome da instância do WhatsApp), em vez de depender que o `tenant_id` seja idêntico ao nome da instância. Isso torna o sistema mais flexível e robusto.
-   **Benefícios:** Sincronização em tempo real, eliminação de erros manuais e maior flexibilidade na configuração.

### Finalização Completa do Pedido (Fluxo MVP)

-   **Problema:** O fluxo de finalização de pedido precisa ser mais robusto e determinístico.
-   **Solução Proposta:**
    1.  **Coleta da Forma de Pagamento:** A IA será instruída a perguntar a forma de pagamento (Pix, Cartão, Dinheiro) após o cliente indicar que deseja fechar o pedido.
    2.  **Resumo Final Determinístico:** O sistema irá gerar um resumo completo do pedido (itens, totais, frete, pagamento) usando uma função em Python, não o LLM, para garantir 100% de precisão.
    3.  **Confirmação Única:** A IA apresentará este resumo para uma confirmação final do cliente.
    4.  **Envio para a Plataforma:** Após a confirmação, o pedido completo é enviado em uma única requisição para a API do `business-whats-dashboard`.
-   **Benefícios:** Experiência do usuário mais clara, eliminação de erros de cálculo pela IA e integração mais confiável entre os sistemas.

## 2. Melhorias Futuras (Pós-MVP)

Esta é uma lista de funcionalidades e melhorias que podem ser implementadas após a estabilização do MVP.

-   **Ativação da Memória Conversacional de Longo Prazo:**
    -   **Descrição:** Ativar a infraestrutura já existente (`services/agents/base_agent.py`) para salvar o histórico completo das conversas no banco de dados vetorial. Isso permitiria à IA lembrar de interações passadas com o mesmo cliente.
    -   **Benefício:** Aumentaria drasticamente a personalização e a capacidade do assistente de responder a perguntas como "o que eu pedi na semana passada?".

-   **Integração com Duckling para Extração de Entidades:**
    -   **Descrição:** Utilizar a biblioteca Duckling (Meta) para extrair de forma determinística entidades como datas, horários, números e durações das mensagens do usuário.
    -   **Benefício:** Reduziria a chance de erros de interpretação da IA em informações críticas como "duas pizzas" ou "entrega para as 19h", tornando o `receptionist_agent` ainda mais confiável.

-   **Integração com Docling para Análise de Mídia:**
    -   **Descrição:** Utilizar a biblioteca Docling (IBM) para processar arquivos complexos, como a transcrição de mensagens de áudio do WhatsApp ou a extração de itens de um cardápio em PDF.
    -   **Benefício:** Permitiria que os lojistas fizessem o upload de seu cardápio em PDF em vez de preencher uma planilha, e possibilitaria que a IA entendesse mensagens de voz dos clientes.

-   **Refinamento do Motor de Regras de Promoções:**
    -   **Descrição:** Expandir a lógica em `services/business_logic/promotion_service.py` para suportar condições e ações de promoção mais complexas (ex: Leve X, Pague Y; descontos progressivos; brindes atrelados a produtos específicos).
    -   **Benefício:** Aumentaria a flexibilidade do sistema de promoções para os lojistas.
