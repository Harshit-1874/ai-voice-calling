import logging
from fastapi import APIRouter, WebSocket, Request, HTTPException
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse
from controllers.call_controller import CallController
from services.websocket_service import WebSocketService
import websockets
from controllers.hubspot_controller import HubspotController

logger = logging.getLogger(__name__)
router = APIRouter()
call_controller = CallController()
websocket_service = WebSocketService()
hubspot_controller = HubspotController()

@router.post("/call/{phone_number}")
async def initiate_call(phone_number: str, request: Request):
    """Initiate a call to the specified phone number."""
    logger.info("="*50)
    logger.info(f"Received call request for phone number: {phone_number}")
    return await call_controller.initiate_call(phone_number, request)

@router.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response."""
    logger.info("="*50)
    logger.info("Received incoming call request")
    return await call_controller.handle_incoming_call(request)

@router.post("/call-status")
async def handle_call_status(request: Request):
    """Handle call status updates from Twilio."""
    logger.info("="*50)
    logger.info("Received call status update")
    return await call_controller.handle_call_status(request)

@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    logger.info("Client connected to media stream")
    await websocket.accept()

    try:
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            extra_headers={
                "Authorization": f"Bearer {websocket_service.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            logger.info("Connected to OpenAI WebSocket")
            await websocket_service.initialize_session(openai_ws)
            await websocket_service.handle_media_stream(websocket, openai_ws)
            
    except Exception as e:
        logger.error(f"Error in media stream: {str(e)}")
    finally:
        logger.info("Client disconnected from media stream")

@router.get("/contacts")
async def list_contacts():
    """Get all contacts from HubSpot."""
    return await hubspot_controller.list_contacts()