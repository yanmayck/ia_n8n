import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
    
# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()
    # Certifique-se de que sua DATABASE_URL está definida no ambiente ou aqui
DATABASE_URL = os.getenv("DATABASE_URL", "SUA_DATABASE_URL_AQUI")
 
try:
    engine = create_engine(DATABASE_URL)
    connection = engine.connect()
    print("Conexão com o banco de dados bem-sucedida!")
    connection.close()
except Exception as e:
    print(f"Erro ao conectar ao banco de dados: {e}")