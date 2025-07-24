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

async def upload_image_to_supabase(file: UploadFile) -> str:
    if not all([SUPABASE_URL, SUPABASE_KEY, SERVICE_ROLE_KEY]):
        raise HTTPException(status_code=500, detail="Configuração do Supabase incompleta no servidor.")

    file_extension = mimetypes.guess_extension(file.content_type)
    file_name = f"{uuid.uuid4()}{file_extension}"
    bucket_name = "menus"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{bucket_name}/{file_name}"

    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": file.content_type
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(upload_url, content=await file.read(), headers=headers)

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
