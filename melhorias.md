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

### 4. Integração com Duckling para Extração de Entidades Estruturadas

- **Descrição:** Integrar a biblioteca Duckling da Meta para extrair entidades estruturadas de forma determinística a partir da mensagem do usuário. Duckling é especializado em reconhecer e converter texto em dados como números, datas, horários, durações e quantidades.
- **Benefício:** Aumentaria drasticamente a confiabilidade do `receptionist_agent`. Em vez de depender do LLM para interpretar "duas pizzas" ou "quero para as sete da noite", o Duckling extrairia dados precisos como `{"value": 2}` ou `{"value": "19:00:00"}`. Isso reduz a chance de erros em informações críticas como quantidades e horários, alinhando-se perfeitamente à filosofia do projeto de usar código determinístico sempre que possível.
- **Implementação Sugerida:** O Duckling poderia ser envolvido em uma nova ferramenta (ex: `extract_entities_tool`). O `receptionist_agent` passaria a mensagem do usuário por essa ferramenta primeiro. O resultado estruturado do Duckling seria então combinado com a análise de intenção geral do LLM para formar um objeto `AnaliseDeIntencao` muito mais preciso e confiável.

### 5. Integração com Docling para Análise de Documentos e Mídia

- **Descrição:** Integrar a biblioteca Docling da IBM Research para processar e converter arquivos complexos em dados estruturados. Diferente do Duckling (que extrai entidades de texto), o Docling é focado em analisar a estrutura e o conteúdo de arquivos como PDFs, DOCX, imagens (com OCR) e áudio.
- **Benefício:**
    - **Cadastro de Cardápio via PDF:** Os lojistas poderiam simplesmente fazer o upload do cardápio em PDF, e o Docling se encarregaria de extrair os itens, descrições e preços, eliminando a necessidade de preencher uma planilha Excel.
    - **Transcrição de Áudio:** O sistema poderia aceitar mensagens de voz do WhatsApp. O Docling faria a transcrição do áudio para texto, que seria então processado pelo `receptionist_agent` como uma mensagem normal. Isso representa um grande avanço na usabilidade e acessibilidade.
    - **Ingestão de Dados Melhorada:** As informações da loja poderiam ser lidas de um arquivo `.docx` ou de um PDF escaneado, tornando o processo de cadastro do tenant mais flexível.
- **Implementação Sugerida:**
    - **No Cadastro:** Usar o Docling na rota de criação/atualização do tenant (`api/routers/tenants.py`) para processar os arquivos de cardápio ou informações da loja.
    - **No Fluxo de Chat:** Integrar o Docling no `services/main_orchestrator.py` como um passo de pré-processamento. Se a mensagem do usuário for um arquivo de áudio, o Docling seria chamado para transcrevê-lo antes de passar o texto para o `receptionist_agent`.
