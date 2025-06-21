import logging
from fastapi import APIRouter, WebSocket, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse
from controllers.call_controller import CallController
from services.websocket_service import WebSocketService
from services.twilio_service import TwilioService
import websockets
from fastapi.responses import Response


logger = logging.getLogger(__name__)
router = APIRouter()
call_controller = CallController()
websocket_service = WebSocketService()
twilio_service = TwilioService()

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
@router.post("/twiml")
async def twiml(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid")
    from_number = form.get("From")
    to_number = form.get("To")
    ws_host = request.url.hostname or "your-ngrok-domain.ngrok-free.app"
    twiml = twilio_service.create_twiml_response(
        ws_host=ws_host,
        from_number=from_number,
        to_number=to_number,
        call_sid=call_sid
    )
    return Response(content=twiml, media_type="text/xml")
@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    logger.info("Client connected to media stream")
    await websocket.accept()

    # Extract call_sid from query parameters
    call_sid = None
    if websocket.query_params:
        call_sid = websocket.query_params.get("call_sid")
        logger.info(f"Call SID from query params: {call_sid}")

    try:
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            extra_headers={
                "Authorization": f"Bearer {websocket_service.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            logger.info("Connected to OpenAI WebSocket")
            await websocket_service.initialize_session(openai_ws, call_sid)
            await websocket_service.handle_media_stream(websocket, openai_ws, call_sid)
            
    except Exception as e:
        logger.error(f"Error in media stream: {str(e)}")
    finally:
        logger.info("Client disconnected from media stream")

@router.get("/call-logs")
async def get_call_logs(limit: int = Query(100, ge=1, le=1000)):
    """Get all call logs with pagination."""
    logger.info("="*50)
    logger.info(f"Getting call logs with limit: {limit}")
    return await call_controller.get_call_logs(limit=limit)

@router.get("/call-logs/{call_sid}")
async def get_call_details(call_sid: str):
    """Get detailed call information including transcriptions."""
    logger.info("="*50)
    logger.info(f"Getting call details for: {call_sid}")
    return await call_controller.get_call_details(call_sid)