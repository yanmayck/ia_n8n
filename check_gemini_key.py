import os

from dotenv import load_dotenv
from google import genai

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Pega a chave da API do ambiente
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Erro: A variável de ambiente GEMINI_API_KEY não foi encontrada.")
    print("Por favor, verifique se o arquivo .env existe e contém a chave.")
else:
    try:
        # --- Alteração para a Nova SDK ---
        # Cria um cliente da API. Se a chave estiver no ambiente,
        # você pode omitir o argumento api_key.
        # client = genai.Client()
        client = genai.Client(api_key=api_key)

        print(
            "Chave de API encontrada. Enviando um prompt de teste para o Gemini com a nova SDK..."
        )

        # --- Alteração para a Nova SDK ---
        # Gera conteúdo usando o cliente, especificando o nome do modelo.
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents="Diga olá."
        )

        # Verifica e imprime a resposta (a estrutura da resposta permanece a mesma)
        print("\n--- Resposta do Gemini ---")
        print(response.text)
        print("--------------------------")
        print(
            "\n✅ Sua chave de API do Gemini é válida e está funcionando corretamente com a nova SDK!"
        )

    except Exception as e:
        print("\n--- Erro ao conectar com a API do Gemini ---")
        print(f"Ocorreu um erro: {e}")
        print(
            "\n❌ Sua chave de API do Gemini é INVÁLIDA ou há um problema de configuração/rede."
        )
        print(
            "Por favor, verifique sua chave no Google AI Studio e as configurações do seu projeto."
        )
