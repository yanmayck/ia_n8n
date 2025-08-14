# Melhorias Futuras (Pós-MVP)

Este arquivo documenta melhorias e novas funcionalidades que podem ser implementadas no futuro, após a estabilização e validação do Produto Mínimo Viável (MVP).

## Lista de Melhorias

### 1. Ativação da Memória Conversacional de Longo Prazo (Arquivo Completo)

- **Descrição:** Atualmente, o sistema possui uma memória de fatos (`PostgresMemoryDb`) que está ativa e funcional. No entanto, a infraestrutura para uma memória episódica completa, que salvaria todas as mensagens de uma conversa em um banco de dados vetorial, já existe em `services/agents/base_agent.py`. As funções responsáveis por isso (`store_conversation_memory` e `retrieve_relevant_memories`) não estão sendo chamadas no fluxo atual.
- **Benefício:** Permitiria à IA responder perguntas complexas sobre o histórico de conversas, como "qual foi o endereço que usei na minha entrega de 2 anos atrás?" ou "o que eu pedi na semana passada?", aumentando drasticamente a personalização e a capacidade do assistente.
- **Implementação Sugerida:** Modificar o workflow em `services/main_orchestrator.py` para adicionar passos que chamem explicitamente as funções de armazenamento e recuperação de memória do `base_agent.py` a cada turno da conversa.

### 2. Implementação de Knowledge Graph para Entidades

- **Descrição:** Aprimorar o sistema de memória para criar um grafo de conhecimento que conecte entidades de forma explícita. Por exemplo, ao identificar a menção "minha filha Ana", o sistema criaria um link entre a entidade `cliente` e a entidade `filha`, com o valor `Ana`.
- **Benefício:** Tornaria a recuperação de informações relacionadas ainda mais rápida, precisa e confiável, sem depender apenas da inferência do LLM em tempo de execução para conectar os pontos.

### 3. Refinamento do Motor de Regras de Promoções

- **Descrição:** Expandir a lógica em `services/business_logic/promotion_service.py` para suportar uma gama maior de condições e ações de promoção a partir da estrutura JSON salva no banco de dados. Exemplos incluem condições de "Leve X, Pague Y", descontos progressivos, ou brindes atrelados a produtos específicos.
- **Benefício:** Aumentaria a flexibilidade do sistema de promoções, permitindo que os donos de loja criem ofertas mais complexas e atrativas sem a necessidade de alterar o código.
