import os
from typing import List, Dict

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma # Importar Chroma da nova biblioteca
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()

# Configuração do embedding model
# Certifique-se de que a GEMINI_API_KEY está configurada no seu .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY não está configurada no ambiente.")

embeddings_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GEMINI_API_KEY)

# Diretório para persistir o ChromaDB
CHROMA_DB_DIR = "./chroma_db"

class VectorDBManager:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.chroma_client = Chroma(
            collection_name=self.collection_name,
            embedding_function=embeddings_model,
            persist_directory=CHROMA_DB_DIR
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, # Tamanho dos pedaços de texto
            chunk_overlap=200 # Sobreposição entre os pedaços
        )

    def add_documents(self, documents: List[str], metadatas: List[Dict] = None):
        # Divide os documentos em chunks
        texts = self.text_splitter.create_documents(documents, metadatas=metadatas)
        self.chroma_client.add_documents(texts)
        self.chroma_client.persist()

    def search_documents(self, query: str, k: int = 3) -> List[Dict]:
        results = self.chroma_client.similarity_search_with_score(query, k=k)
        
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "page_content": doc.page_content,
                "metadata": doc.metadata,
                "score": score
            })
        return formatted_results

    def delete_collection(self):
        """Deleta a coleção inteira do ChromaDB."""
        self.chroma_client.delete_collection()