import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Form
from datetime import timedelta

from api.dependencies import create_access_token

router = APIRouter()
logger = logging.getLogger(__name__)

ACCESS_TOKEN_EXPIRE_MINUTES = 30

@router.post("/login", tags=["Authentication"])
def login(password: str = Form(...)):
    """Endpoint para autenticação de administrador."""
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        logger.error("ADMIN_PASSWORD não configurada no ambiente.")
        raise HTTPException(status_code=500, detail="Senha de administrador não configurada.")

    if password == admin_password:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": "admin"}, expires_delta=access_token_expires
        )
        logger.info("Login de administrador bem-sucedido. Token gerado.")
        return {"message": "Login bem-sucedido", "access_token": access_token, "token_type": "bearer"}
    else:
        logger.warning("Tentativa de login de administrador falhou.")
        raise HTTPException(status_code=401, detail="Senha incorreta.")
