# Plano de Ação: Finalização do Pedido (MVP)

## 1. Visão Geral

Este documento detalha as modificações necessárias nos projetos `ia_n8n` e `business-whats-dashboard` para implementar o fluxo de finalização de pedido.

O objetivo é criar um fluxo de conversação onde a IA:
1.  Coleta os itens do pedido.
2.  Pergunta a forma de pagamento.
3.  Apresenta um resumo completo (itens, valores, frete, forma de pagamento) para uma confirmação final.
4.  Cria o pedido completo no `business-whats-dashboard` em uma **única requisição** após a confirmação do cliente.

## 2. Fluxo de Conversa do Usuário

A interação ideal será a seguinte:

1.  **Cliente:** "Gostaria de uma pizza de calabresa e um refrigerante."
2.  **IA:** "Anotado! Algo mais?"
3.  **Cliente:** "só isso, pode fechar a conta."
4.  **IA:** "Ok! E como você gostaria de pagar? Aceitamos Pix, Dinheiro ou Cartão."
5.  **Cliente:** "pode ser no pix"
6.  **IA:** "Combinado! Para confirmar, seu pedido ficou assim:

```
*Resumo do Pedido:*
-----------------------------------
- 1x Pizza de Calabresa.... R$ 45,50
- 1x Refrigerante 2L......... R$ 10,00
-----------------------------------
*Subtotal:* R$ 55,50
*Taxa de Entrega:* R$ 5,00
*TOTAL:* *R$ 60,50*

*Pagamento:* Pix
```

Está tudo correto?"
7.  **Cliente:** "sim"
8.  **IA:** "Perfeito! Seu pedido foi confirmado e já está sendo preparado. Agradecemos a preferência!"

## 3. Modificações no `ia_n8n`

### 3.1. `core/schemas.py`

- No schema `OrderState`, adicione um campo para armazenar o método de pagamento durante a conversa.

```python
class OrderState(BaseModel):
    items: List[OrderItem] = Field(default_factory=list)
    address: Optional[str] = None
    status: str = "open"
    payment_method: Optional[str] = None # <-- ADICIONAR ESTE CAMPO
    # ... outros campos
```

### 3.2. `services/agents/receptionist_agent.py`

- Atualize o prompt do agente para que ele possa identificar a escolha de um método de pagamento e gerar uma nova tarefa.
- **Nova Tarefa:** `tipo_tarefa: 'informar_metodo_pagamento'`, `detalhes: 'pix' | 'cartao' | 'dinheiro'`.

### 3.3. `services/main_orchestrator.py`

Esta é a mudança principal. O workflow será reestruturado para seguir o novo fluxo, utilizando o `Router` do Agno para direcionar a conversa.

#### Etapa 3.3.1: Implementar a Pergunta sobre a Forma de Pagamento

Quando o cliente pede para "fechar a conta", a IA deve primeiro perguntar como ele deseja pagar.

1.  **Definir o novo `Step` no Orquestrador:**
    No método `__init__` da classe `OrchestratorAgent`, defina um novo `Step` cuja única função é lidar com a pergunta da forma de pagamento.

    ```python
    # Em services/main_orchestrator.py, dentro de OrchestratorAgent.__init__
    
    self.ask_payment_method_step = Step(
        name="ask_payment_method",
        executor=partial(self._ask_payment_method_executor)
    )
    ```

2.  **Criar a Função `Executor`:**
    Crie a função que será executada por este `Step`. A responsabilidade dela não é gerar a pergunta, mas sim passar uma instrução clara para o `response_formulation_agent`.

    ```python
    # Em services/main_orchestrator.py, dentro da classe OrchestratorAgent

    async def _ask_payment_method_executor(self, step_input: StepInput) -> StepOutput:
        """
        Prepara o contexto para o agente de formulação de resposta perguntar
        a forma de pagamento.
        """
        logger.info("EXECUTOR: Preparando para perguntar a forma de pagamento.")
        
        # Instrução clara que será usada pelo agente de formulação da resposta
        context_message = "O cliente pediu para fechar o pedido. Pergunte a ele qual a forma de pagamento (Pix, Cartão ou Dinheiro) e aguarde a resposta."
        
        # Usamos o 'rag_context' para passar a instrução para o próximo passo.
        step_input.additional_data["rag_context"] = context_message
        
        return StepOutput(content=context_message)
    ```

3.  **Atualizar o `Router`:**
    Modifique a função `_route_to_data_collection_step` para que, ao receber a intenção `fechar_conta`, ela acione o `ask_payment_method_step`.

    ```python
    # Em services/main_orchestrator.py, dentro de _route_to_data_collection_step

    task_types = {t.tipo_tarefa for t in receptionist_output.tarefas}

    if "fechar_conta" in task_types:
        logger.info("Roteando para o passo de perguntar a forma de pagamento.")
        # Adicione o novo step à lista de choices do Router e retorne-o aqui
        return self.ask_payment_method_step 
    
    # ... resto da lógica do roteador
    ```

#### Etapa 3.3.2: Implementar a Confirmação Final e Criação do Pedido

Após o cliente responder a forma de pagamento, o fluxo continua.

1.  **Intenção de Finalizar:** Quando o `receptionist_agent` detectar a forma de pagamento (ex: `tipo_tarefa: 'informar_metodo_pagamento'`), o roteador deve acionar o `final_confirmation_step`.

2.  **Passo `final_confirmation_step`:**
    -   **Lógica:**
        - Recupera o `OrderState` completo da memória (Redis).
        - Adiciona o `payment_method` ao estado.
        - **Chama a função `formatar_resumo_pedido` (descrita na seção 3.5) para montar a string de resumo completa.**
        - Passa essa string para o `response_formulation_agent` com a instrução de apresentá-la e pedir a confirmação final ("Está tudo correto?").

3.  **Passo Final - `create_order_step`:**
    -   Será acionado quando o usuário responder "sim" à confirmação final.
    -   **Lógica:**
        - Chama a função `save_order_to_platform` com todos os dados do `OrderState`, incluindo o `payment_method`.
        - Gera a mensagem de despedida.

### 3.4. `services/integrations/platform_client.py`

- Modifique a função `save_order_to_platform` para que ela inclua o `payment_method` no corpo da requisição `POST` enviada para a API do dashboard.

### 3.5. Geração do Resumo do Pedido (Determinístico)

Para garantir a precisão dos valores e evitar erros da IA, o resumo final do pedido será gerado por uma função em Python, não pelo LLM.

- **Ação:** Criar uma função auxiliar (ex: em `services/utils.py` ou no próprio `main_orchestrator.py`) que recebe o estado do pedido e retorna uma string de resumo formatada.

- **Exemplo da Função:**
  ```python
  def formatar_resumo_pedido(order_state: OrderState, freight_details: Optional[FreightDetails]) -> str:
      resumo = "*Resumo do Pedido:*
"
      resumo += "-----------------------------------
"
      subtotal = 0
      for item in order_state.items:
          preco_item = item.total_price
          subtotal += preco_item
          resumo += f"- {item.quantity}x {item.product_name}.... R$ {preco_item:.2f}\n".replace('.', ',')
      
      resumo += "-----------------------------------
"
      resumo += f"*Subtotal:* R$ {subtotal:.2f}
".replace('.', ',')
      
      frete = freight_details.cost if freight_details else 0.0
      resumo += f"*Taxa de Entrega:* R$ {frete:.2f}
".replace('.', ',')
      
      total = subtotal + frete
      resumo += f"*TOTAL:* *R$ {total:.2f}*

".replace('.', ',')
      
      if order_state.payment_method:
          resumo += f"*Pagamento:* {order_state.payment_method.capitalize()}"
      
      return resumo
  ```

- **Lógica do Orquestrador:** O `final_confirmation_step` no orquestrador irá:
  1. Chamar esta função `formatar_resumo_pedido`.
  2. Passar a string resultante e já formatada para o `response_formulation_agent`.
  3. A instrução para o agente de resposta será apenas para adicionar uma saudação e pedir a confirmação (ex: "Ok, para confirmar... [string do resumo]... Está correto?").


## 4. Modificações no `business-whats-dashboard`

### 4.1. `prisma/schema.prisma`

- Adicione o campo `payment_method` ao modelo `pedidos` para armazenar a escolha do cliente.

```prisma
model pedidos {
  // ... outros campos
  payment_method String?
}
```
- Execute `npx prisma migrate dev --name add_payment_method_to_orders` para aplicar a migração.

### 4.2. Backend (API)

- **`backend/database/pedidos.ts`:** Atualize a função `criarPedido` para que ela aceite e salve o novo campo `payment_method`.
- **`backend/routes/pedidos.ts`:** Na rota `POST /api/pedidos`, certifique-se de que o `payment_method` vindo do corpo da requisição seja passado para a função `criarPedido`.

### 4.3. Frontend (Interface)

- As alterações na interface são para **visualização**.
- **`frontend/src/components/order-card.tsx`:** Adicione um ícone ou um texto pequeno no card para mostrar rapidamente a forma de pagamento escolhida (ex: "Pagamento: Pix").
- **`frontend/src/components/order-details-modal.tsx`:** No modal de detalhes, adicione um campo claro e legível para exibir a "Forma de Pagamento" junto com as outras informações do pedido.
