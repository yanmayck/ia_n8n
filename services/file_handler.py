import os
import logging
from fastapi import HTTPException, UploadFile
import httpx
import uuid
import mimetypes

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")

import os
import logging
from fastapi import HTTPException, UploadFile
import httpx
import uuid
import mimetypes
from PIL import Image
import io

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY")

async def optimize_image(file_content: bytes, max_size: tuple = (1600, 1600), quality: int = 85) -> bytes:
    """Otimiza uma imagem redimensionando e comprimindo."""
    try:
        img = Image.open(io.BytesIO(file_content))
        img.thumbnail(max_size)
        
        # Converte para RGB para salvar como JPEG
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"Erro ao otimizar imagem: {e}")
        return file_content # Retorna o original em caso de erro

async def upload_image_to_supabase(file: UploadFile) -> str:
    if not all([SUPABASE_URL, SUPABASE_KEY, SERVICE_ROLE_KEY]):
        raise HTTPException(status_code=500, detail="Configuração do Supabase incompleta no servidor.")

    file_content = await file.read()
    optimized_content = await optimize_image(file_content)

    file_name = f"{uuid.uuid4()}.jpg" # Salva como JPG otimizado
    bucket_name = "menus"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{bucket_name}/{file_name}"

    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "image/jpeg"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(upload_url, content=optimized_content, headers=headers)

    if response.status_code != 200:
        logger.error(f"Erro no upload para o Supabase: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=f"Erro no upload da imagem: {response.text}")

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_name}"
    logger.info(f"Imagem enviada com sucesso para: {public_url}")
    return public_url

async def delete_image_from_supabase(image_url: str):
    if not all([SUPABASE_URL, SUPABASE_KEY, SERVICE_ROLE_KEY]):
        raise HTTPException(status_code=500, detail="Configuração do Supabase incompleta no servidor.")

    bucket_name = "menus"
    file_name = image_url.split(f"/{bucket_name}/")[-1]
    delete_url = f"{SUPABASE_URL}/storage/v1/object/{bucket_name}/{file_name}"

    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.delete(delete_url, headers=headers)

    if response.status_code != 200:
        logger.warning(f"Falha ao deletar imagem antiga do Supabase: {response.text}")
    else:
        logger.info(f"Imagem antiga deletada com sucesso: {image_url}")
