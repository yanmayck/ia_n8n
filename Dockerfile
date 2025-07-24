# Usa uma imagem base Python com um sistema operacional Debian leve (buster)
# Esta imagem é geralmente uma boa escolha, pois inclui ferramentas básicas e é otimizada.
FROM python:3.10-slim-bookworm

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de requisitos para o diretório de trabalho
COPY requirements.txt .

# Instala as dependências do sistema operacional necessárias para as libs Python
# e outras ferramentas como git. Separar em camadas melhora o cache e a depuração.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    pigz \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências do sistema, como o ffmpeg para processamento de vídeo.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Limpa o cache do pip e instala as dependências Python a partir do arquivo de requisitos
RUN pip cache purge && pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da sua aplicação para o diretório de trabalho
# O '.' no final significa o diretório atual do host.
# O .dockerignore garantirá que arquivos como .env não sejam copiados.
COPY . .

# Expor a porta em que sua aplicação FastAPI será executada
EXPOSE 8000

# Comando para iniciar sua aplicação FastAPI
# Lembre-se que 'api.main:app' significa o arquivo 'main.py' dentro da pasta 'api',
# e 'app' é a instância do FastAPI.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"] 