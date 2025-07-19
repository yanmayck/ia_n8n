
# Documentação da Biblioteca `agno`

`agno` é um framework de código aberto em Python para a construção de sistemas de múltiplos agentes. Ele foi projetado para ser leve, rápido e agnóstico de modelo, permitindo que os desenvolvedores criem agentes que podem lidar com vários tipos de dados, incluindo texto, imagens, áudio e vídeo.

## Filosofia Principal

A filosofia central do `agno` gira em torno da simplicidade e do desempenho, evitando estruturas complexas em favor de uma experiência de desenvolvimento mais direta e em "Python puro". Ele equipa os agentes com capacidades como memória, bases de conhecimento para Geração Aumentada por Recuperação (RAG), raciocínio e a habilidade de usar ferramentas.

## Principais Características

*   **Alto Desempenho**: O framework é otimizado para velocidade e um baixo consumo de memória, com a instanciação de agentes levando apenas alguns microssegundos.
*   **Agnóstico de Modelo**: Ele fornece uma interface unificada que suporta mais de 23 provedores de modelos, evitando a dependência de um único fornecedor.
*   **Arquitetura de Múltiplos Agentes**: `agno` suporta a criação de equipes de agentes especializados que podem colaborar em tarefas complexas.
*   **Saídas Estruturadas**: Os agentes podem ser configurados para retornar dados estruturados e totalmente tipados.
*   **Integrações**: Possui suporte integrado para vários bancos de dados vetoriais e pode ser integrado a serviços como o Langtrace para monitoramento e observabilidade.

## Instalação

Você pode instalar o `agno` usando o pip:

```bash
pip install agno
```

A biblioteca também possui pacotes relacionados para integrações específicas, como `agno-aws`, e ferramentas como `agno-yaml-builder` para definir estruturas de agentes em arquivos YAML.

## Como Usar

(Esta seção seria preenchida com exemplos de código mais detalhados, mas com base na pesquisa inicial, aqui está um exemplo conceitual de como você poderia usar o `agno`.)

### 1. Definindo um Agente

Primeiro, você definiria um agente e suas ferramentas. O `agno` permite que você use decoradores para registrar funções como ferramentas que o agente pode usar.

```python
from agno import Agent

# Crie uma instância do agente
meu_agente = Agent(name="assistente_de_pesquisa")

# Defina uma ferramenta que o agente pode usar
@meu_agente.tool
def pesquisar_na_web(query: str) -> str:
    """Pesquisa na web pela query fornecida."""
    # (aqui você implementaria a lógica de pesquisa na web)
    return f"Resultados da pesquisa para: {query}"
```

### 2. Interagindo com o Agente

Depois de definir o agente e suas ferramentas, você pode interagir com ele passando prompts.

```python
# Interaja com o agente
resposta = meu_agente.act("Pesquise sobre os últimos avanços em IA.")

print(resposta)
```

### 3. Múltiplos Agentes

O `agno` permite que você crie múltiplos agentes que podem colaborar.

```python
# Crie múltiplos agentes
pesquisador = Agent(name="pesquisador")
escritor = Agent(name="escritor")

# Defina as ferramentas para cada agente
@pesquisador.tool
def pesquisar(query: str) -> str:
    # ...

@escritor.tool
def escrever_artigo(topico: str, pontos_chave: list) -> str:
    # ...

# Orquestre a colaboração entre os agentes
resultados_pesquisa = pesquisador.act("Pesquise sobre os benefícios da energia solar.")
artigo_final = escritor.act(f"Escreva um artigo sobre os benefícios da energia solar usando os seguintes pontos: {resultados_pesquisa}")

print(artigo_final)
```

## Conclusão

`agno` parece ser uma biblioteca promissora para a construção de sistemas de IA baseados em agentes, especialmente para casos de uso que exigem alto desempenho e a flexibilidade de usar diferentes modelos de linguagem. Sua abordagem minimalista e foco no "Python puro" podem torná-lo uma alternativa atraente a frameworks mais complexos.
