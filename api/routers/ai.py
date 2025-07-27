import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
import base64
import mimetypes
import httpx

from crud import tenant_crud, interaction_crud, menu_image_crud
from core import schemas
from services import chat_service, google_maps_service, file_handler
from api.dependencies import get_db, get_current_user
from core.database import SessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/ai", response_model=List[schemas.AIWebhookResponsePart], tags=["IA"])
async def handle_ai_webhook(request: Request, db: Session = Depends(get_db)):
    logger.info("ROTA /ai ACESSADA!")
    try:
        request_body = await request.json()
        logger.info(f"RAW REQUEST BODY RECEIVED: {request_body}")
        
        try:
            request_data = {
                "message_user": request_body.get("message_user", ""),
                "message_base64": request_body.get("message_base64", ""),
                "mimetype": request_body.get("mimetype"),
                "tenant_id": request_body.get("tenant_id"),
                "user_phone": request_body.get("user_phone"),
                "whatsapp_message_id": request_body.get("whatsapp_message_id"),
                "latitude": request_body.get("latitude"),
                "longitude": request_body.get("longitude")
            }
            ai_request = schemas.AIWebhookRequest(**request_data)
            logger.info(f"Request body validated successfully: {ai_request.model_dump_json(indent=2)}")
        except ValidationError as e:
            logger.error(f"PYDANTIC VALIDATION ERROR: {e.errors()}", exc_info=True)
            raise HTTPException(status_code=422, detail=e.errors())

        tenant = await run_in_threadpool(tenant_crud.get_tenant_by_id, db, tenant_id=ai_request.tenant_id)
        if not tenant or not tenant.is_active:
            logger.error(f"Tenant com ID '{ai_request.tenant_id}' não encontrado ou inativo.")
            raise HTTPException(status_code=404, detail=f"Cliente com o ID '{ai_request.tenant_id}' não foi encontrado ou está inativo.")

        personality_prompt = tenant.personality.prompt if tenant.personality and tenant.personality.prompt else "Você é um assistente de IA prestativo."
        
        file_content = None
        mimetype = None
        if ai_request.message_base64 and ai_request.mimetype:
            try:
                file_content = base64.b64decode(ai_request.message_base64)
                mimetype = ai_request.mimetype
                logger.info(f"Mensagem com mídia recebida. Mimetype: {mimetype}, Tamanho: {len(file_content)} bytes")
            except Exception as e:
                logger.error(f"Erro ao decodificar a mensagem em base64: {e}", exc_info=True)
        
        logger.info(f"Chamando chat_service.handle_message com os seguintes parâmetros:")
        # ... (logs de debug)

        ai_result = await chat_service.handle_message(
            user_id=ai_request.user_phone,
            session_id=ai_request.whatsapp_message_id,
            message=ai_request.message_user,
            tenant_id=ai_request.tenant_id,
            personality_prompt=personality_prompt,
            file_content=file_content,
            mimetype=mimetype,
            client_latitude=ai_request.latitude,
            client_longitude=ai_request.longitude
        )

        logger.info(f"Resposta Estruturada da IA: {ai_result}")

        response_parts = []
        text_response = ai_result.get("response_text")
        human_handoff = ai_result.get("human_handoff", False)
        send_menu = ai_result.get("send_menu", False)

        if not isinstance(text_response, str):
            text_response = str(text_response)

        if text_response:
            response_parts.append({
                "part_id": 1,
                "type": "text",
                "text_content": text_response,
                "human_handoff": False,
                "send_menu": False
            })

        if send_menu:
            latest_image = await run_in_threadpool(menu_image_crud.get_latest_menu_image_by_tenant, db, tenant.tenant_id)
            if latest_image and latest_image.image_url:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(latest_image.image_url)
                        response.raise_for_status()
                        optimized_content = await file_handler.optimize_image(response.content)
                        image_base64 = base64.b64encode(optimized_content).decode("utf-8")

                    response_parts.append({
                        "part_id": len(response_parts) + 1,
                        "type": "file",
                        "human_handoff": False,
                        "send_menu": True,
                        "file_details": {
                            "retrieval_key": "menu_image",
                            "file_type": "image/jpeg",
                            "base64_content": image_base64
                        }
                    })
                except Exception as e:
                    logger.error(f"Erro ao baixar ou processar imagem do cardápio: {e}", exc_info=True)
            else:
                logger.warning(f"send_menu era True, mas nenhuma imagem de cardápio foi encontrada para o tenant {tenant.tenant_id}")
        
        if human_handoff:
            response_parts.append({
                "part_id": len(response_parts) + 1,
                "type": "validation",
                "human_handoff": True,
                "send_menu": False
            })

        if not response_parts:
            logger.warning("Nenhuma parte de resposta foi gerada pela IA.")

        return response_parts

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.critical(f"Erro crítico na rota /ai: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {str(e)}")

@router.post("/calcular-frete", dependencies=[Depends(get_current_user)])
async def calcular_frete(
    tenant_id: str,
    cliente_lat: float,
    cliente_lng: float,
    db: Session = Depends(get_db)
):
    logger.info(f"Calculando frete para tenant {tenant_id} e cliente ({cliente_lat}, {cliente_lng})")
    tenant = tenant_crud.get_tenant_by_id(db, tenant_id)
    if not tenant:
        logger.warning(f"Tentativa de calcular frete para cliente não encontrado: {tenant_id}")
        raise HTTPException(status_code=404, detail="Cliente/loja não encontrado")
    
    if not tenant.latitude or not tenant.longitude:
        logger.warning(f"Loja {tenant_id} não possui coordenadas cadastradas para cálculo de frete.")
        raise HTTPException(status_code=400, detail="Loja não possui coordenadas cadastradas")
    
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
    if not GOOGLE_MAPS_API_KEY:
        logger.error("Google Maps API Key não configurada para cálculo de frete.")
        raise HTTPException(status_code=400, detail="Google Maps API Key não configurada")
    
    try:
        distancia_km = await google_maps_service.calcular_frete_google_maps_async(
            float(tenant.latitude), 
            float(tenant.longitude), 
            cliente_lat, 
            cliente_lng, 
            GOOGLE_MAPS_API_KEY
        )
        logger.info(f"Frete calculado para {tenant_id}: {distancia_km:.2f} km.")
        return {
            "distancia_km": distancia_km,
            "origem": {
                "endereco": tenant.endereco,
                "latitude": tenant.latitude,
                "longitude": tenant.longitude
            },
            "destino": {
                "latitude": cliente_lat,
                "longitude": cliente_lng
            }
        }
    except Exception as e:
        logger.error(f"Erro ao calcular frete para {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao calcular frete: {str(e)}")