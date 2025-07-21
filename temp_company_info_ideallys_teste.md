=====================================================
== Resumo do Projeto e Identidade da Empresa         ==
=====================================================

Arquivo gerado em: 19 de julho de 2025

---
### 1. Identidade da Empresa
---

* **Nome da Empresa:** LogiCore

* **Slogan/Tagline Sugerido:** "A lógica por trás dos seus resultados."
    * Alternativas: "Inteligência que transforma processos.", "O núcleo da sua automação."

* **Conceito Principal:** Empresa de tecnologia (B2B) focada em desenvolver soluções de automação e inteligência artificial para otimizar processos, aumentar a eficiência, escalar operações e reduzir custos para outras empresas.

* **Imagem a ser Transmitida:** Moderna, tecnológica, inteligente, eficiente e central (core) para as operações do cliente.

---
### 2. Primeiro Produto (Foco Inicial)
---

* **Conceito do Produto:** Um sistema de atendimento automatizado por IA para o setor de food service (lanchonetes, pizzarias, restaurantes de sushi, etc.).

* **Funcionalidades Chave:**
    * Anotar pedidos de clientes de forma autônoma.
    * Fazer recomendações de produtos com base em perguntas.
    * Adaptável a diferentes tipos de cardápios.

* **Tecnologia Base (Discutida):**
    * Uso de RAG (Retrieval-Augmented Generation).
    * Uso de Banco de Dados Vetorial para fazer buscas por similaridade nos cardápios e encontrar produtos de forma inteligente.

---
### 3. Infraestrutura e Ambiente de Desenvolvimento (DevOps)
---

* **Controle de Versão:**
    * Git para controle local.
    * GitHub para repositório remoto.

* **Editor de Código:**
    * Cursor (fork do VS Code com foco em IA).

* **Ambiente de Desenvolvimento Local:**
    * **Aplicação Principal ("evolution"):** Roda localmente na porta 8080 e requer conexão HTTPS (`https://localhost:8080`).
    * **Exposição para a Internet (Túnel):** Ngrok.
    * **Comando de Execução do Ngrok (testado e funcional):** `ngrok http https://localhost:8080`
    * **Proxy Reverso (para testes com sub-rotas):** Caddy (configurado para escutar em uma porta separada, ex: 9000, e redirecionar para a aplicação).
    * **Containerização:** Docker.

* **Problemas Técnicos Resolvidos:**
    * Conflitos de protocolo (HTTP vs. HTTPS) entre Ngrok, Caddy e a aplicação.
    * Problemas de "tela branca" relacionados a rotas de assets (JS/CSS) em aplicações rodando sob um sub-caminho no proxy.
    * Erros de instalação de pacotes (`ENOENT` no Cursor, versão antiga do Ngrok no Winget).

---
### 4. Pessoas e Contexto
---

* **Fundador/Desenvolvedor Principal:** Yan.
* **Contexto Acadêmico/Investimento:** Apresentação da startup para professores da USP que investem em novos projetos.
* **Equipe:** Decisões de branding e estratégia a serem discutidas com a equipe.

=====================================================
== Fim do Resumo                                   ==
=====================================================