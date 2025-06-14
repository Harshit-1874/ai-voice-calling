import os
import json
import base64
import asyncio
import websockets
import logging
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    if not TWILIO_ACCOUNT_SID:
        raise ValueError("TWILIO_ACCOUNT_SID environment variable is not set")
    if not TWILIO_AUTH_TOKEN:
        raise ValueError("TWILIO_AUTH_TOKEN environment variable is not set")
    if not TWILIO_PHONE_NUMBER:
        raise ValueError("TWILIO_PHONE_NUMBER environment variable is not set")
    
    logger.info("Starting server...")
    logger.info(f"Server running at {BASE_URL}")
    yield
    logger.info("Shutting down server...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_phone_number(number: str) -> str:
    cleaned = ''.join(c for c in number if c.isdigit() or c == '+')
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    return cleaned

@app.post("/call/{phone_number}")
async def initiate_call(phone_number: str):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        to_number = clean_phone_number(phone_number)
        from_number = clean_phone_number(TWILIO_PHONE_NUMBER)
        
        logger.info(f"Initiating call from {from_number} to {to_number}")
        
        base_url = BASE_URL.rstrip('/')
        
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            url=f"{base_url}/incoming-call",
            status_callback=f"{base_url}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed']
        )
        
        logger.info(f"Call initiated with SID: {call.sid}")
        
        return {
            "message": "Call initiated",
            "call_sid": call.sid,
            "to": to_number,
            "from": from_number,
            "status": "initiated"
        }
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error initiating call: {error_message}")
        logger.error(f"Full error details: {repr(e)}")
        raise HTTPException(status_code=500, detail=error_message)

@app.post("/incoming-call")
async def handle_incoming_call(request: Request):
    try:
        form_data = await request.form()
        logger.info(f"Incoming call request: {form_data}")
        
        response = VoiceResponse()
        response.connect().stream(url=f"wss://{request.url.netloc}/media-stream")
        
        logger.info(f"Generated TwiML response: {str(response)}")
        return str(response)
    except Exception as e:
        logger.error(f"Error handling incoming call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to media stream")
    
    try:
        openai_ws = None
        session_id = None
        
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")
            
            if event == "start":
                logger.info("Received start event from Twilio")
                openai_ws = await websockets.connect("wss://api.openai.com/v1/audio/realtime")
                await send_session_update(openai_ws)
                session_id = data.get("start", {}).get("callSid")
                logger.info(f"Created OpenAI session with ID: {session_id}")
            
            elif event == "media":
                if not openai_ws:
                    logger.error("Received media event before start")
                    continue
                
                payload = data.get("media", {}).get("payload")
                if payload:
                    chunk = base64.b64decode(payload)
                    await openai_ws.send(chunk)
                    logger.debug("Sent audio chunk to OpenAI")
            
            elif event == "stop":
                logger.info("Received stop event from Twilio")
                if openai_ws:
                    await openai_ws.close()
                    openai_ws = None
                break
            
            if openai_ws:
                try:
                    response = await asyncio.wait_for(openai_ws.recv(), timeout=0.1)
                    if response:
                        await websocket.send_text(response)
                        logger.debug("Sent response from OpenAI to Twilio")
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error receiving from OpenAI: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in media stream: {str(e)}")
    finally:
        if openai_ws:
            await openai_ws.close()
        logger.info("Client disconnected from media stream")

async def send_session_update(websocket):
    config = {
        "audio_format": "mulaw",
        "sample_rate": 8000,
        "chunk_size": 640,
        "instructions": "You are a helpful AI assistant. Respond naturally and concisely.",
        "model": "gpt-4",
        "language": "en"
    }
    await websocket.send(json.dumps({"type": "session.update", "data": config}))

@app.post("/call-status")
async def call_status(request: Request):
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        
        logger.info(f"Call status update - SID: {call_sid}, Status: {call_status}")
        logger.info(f"From: {from_number}, To: {to_number}")
        
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error processing call status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-call")
async def test_call():
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        verified_numbers = client.outgoing_caller_ids.list()
        verified_numbers_list = [clean_phone_number(number.phone_number) for number in verified_numbers]
        logger.info(f"Verified numbers: {verified_numbers_list}")
        
        from_number = clean_phone_number("+447808221001")
        to_number = clean_phone_number("+917973539086")
        
        logger.info(f"Making test call from {from_number} to {to_number}")
        
        base_url = BASE_URL.rstrip('/')
        
        if from_number not in verified_numbers_list:
            logger.error(f"From number {from_number} is not in verified numbers list")
            raise HTTPException(
                status_code=400,
                detail=f"From number {from_number} is not verified. Please verify it in the Twilio Console first."
            )
        
        if to_number not in verified_numbers_list:
            logger.error(f"To number {to_number} is not in verified numbers list")
            raise HTTPException(
                status_code=400,
                detail=f"To number {to_number} is not verified. Please verify it in the Twilio Console first."
            )
        
        response = VoiceResponse()
        response.say("Hello! This is a test call from your AI Voice Calling system.")
        response.pause(length=1)
        response.say("Thank you for testing the system.")
        
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml=str(response),
            status_callback=f"{base_url}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed']
        )
        
        logger.info(f"Test call initiated with SID: {call.sid}")
        
        return {
            "message": "Test call initiated",
            "call_sid": call.sid,
            "to": to_number,
            "from": from_number,
            "status": "initiated",
            "verified_numbers": verified_numbers_list
        }
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error initiating test call: {error_message}")
        logger.error(f"Full error details: {repr(e)}")
        raise HTTPException(status_code=500, detail=error_message)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT) 