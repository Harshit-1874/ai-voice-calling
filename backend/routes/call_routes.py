import logging
import json
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

@router.post("/recording-callback")
async def handle_recording_callback(request: Request):
    """Handle recording completion callback from Twilio."""
    try:
        form_data = await request.form()
        logger.info(f"Recording callback received: {dict(form_data)}")
        
        call_sid = form_data.get("CallSid")
        recording_sid = form_data.get("RecordingSid")
        recording_url = form_data.get("RecordingUrl")
        recording_duration = form_data.get("RecordingDuration")
        
        if call_sid and recording_url:
            # Store recording information in database
            async with call_controller.prisma_service:
                call_log = await call_controller.prisma_service.get_call_log(call_sid)
                if call_log:
                    # Update call log with recording information
                    await call_controller.prisma_service.prisma.calllog.update(
                        where={"id": call_log.id},
                        data={
                            "recordingUrl": recording_url,
                            "duration": int(recording_duration) if recording_duration else None
                        }
                    )
                    logger.info(f"Updated call log {call_log.id} with recording URL: {recording_url}")
        
        # Return empty TwiML to continue the call
        response = VoiceResponse()
        return Response(content=str(response), media_type="text/xml")
        
    except Exception as e:
        logger.error(f"Error handling recording callback: {str(e)}")
        # Return empty TwiML even on error
        response = VoiceResponse()
        return Response(content=str(response), media_type="text/xml")

@router.post("/transcription-callback")
async def handle_transcription_callback(request: Request):
    """Handle transcription completion callback from Twilio."""
    try:
        form_data = await request.form()
        logger.info(f"Transcription callback received: {dict(form_data)}")
        
        # Extract relevant data from the callback
        call_sid = form_data.get("CallSid")
        recording_sid = form_data.get("RecordingSid")
        transcription_sid = form_data.get("TranscriptionSid")
        transcription_text = form_data.get("TranscriptionText", "")
        transcription_status = form_data.get("TranscriptionStatus")
        confidence = form_data.get("Confidence")
        
        logger.info(f"Transcription for call {call_sid}: {transcription_text}")
        
        if call_sid and transcription_text and transcription_status == "completed":
            # Use enhanced transcription service to process Twilio transcription
            confidence_float = float(confidence) if confidence else None
            recording_url = form_data.get("RecordingUrl")
            
            success = await call_controller.transcription_service.process_twilio_transcription(
                call_sid=call_sid,
                transcription_text=transcription_text,
                confidence=confidence_float,
                recording_url=recording_url
            )
            
            if success:
                logger.info(f"✅ Successfully processed Twilio transcription for call {call_sid} via enhanced service")
                
                # Optionally create conversation analysis
                try:
                    async with call_controller.prisma_service:
                        call_log = await call_controller.prisma_service.get_call_log(call_sid)
                        if call_log:
                            summary = f"Call transcription: {transcription_text[:100]}..." if len(transcription_text) > 100 else transcription_text
                            
                            await call_controller.prisma_service.create_conversation_analysis(
                                call_log_id=call_log.id,
                                summary=summary,
                                sentiment="neutral",
                                lead_score=5,
                                next_action="Review transcription and follow up if needed"
                            )
                            logger.info(f"Created conversation analysis for call {call_sid}")
                except Exception as analysis_error:
                    logger.warning(f"Could not create conversation analysis: {str(analysis_error)}")
            else:
                logger.error(f"❌ Failed to process Twilio transcription for call {call_sid}")
        
        elif transcription_status == "failed":
            logger.error(f"Transcription failed for call {call_sid}")
        
        # Always return 200 OK to Twilio
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error handling transcription callback: {str(e)}")
        # Always return 200 OK to Twilio even on error
        return {"status": "success"}
@router.get("/call-logs/{call_sid}/transcriptions")
async def get_call_transcriptions(call_sid: str):
    """Get all transcriptions for a specific call."""
    logger.info(f"Getting transcriptions for call: {call_sid}")
    try:
        async with call_controller.prisma_service:
            call_log = await call_controller.prisma_service.get_call_log(call_sid)
            if not call_log:
                raise HTTPException(status_code=404, detail="Call not found")
            
            transcriptions = await call_controller.prisma_service.prisma.transcription.find_many(
                where={"callLogId": call_log.id},
                order={"timestamp": "asc"}
            )
            
            return {
                "call_sid": call_sid,
                "total_transcriptions": len(transcriptions),
                "transcriptions": [
                    {
                        "id": t.id,
                        "speaker": t.speaker,
                        "text": t.text,
                        "confidence": t.confidence,
                        "timestamp": t.timestamp.isoformat(),
                        "is_final": t.isFinal
                    }
                    for t in transcriptions
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/start-recording/{call_sid}")
async def start_recording(call_sid: str):
    """Start recording for an in-progress call."""
    try:
        logger.info(f"Starting recording for call: {call_sid}")
        
        # Create recording TwiML
        recording_twiml = twilio_service.create_recording_twiml_response(call_sid)
        
        # Update the call with recording TwiML
        try:
            call = twilio_service.client.calls(call_sid).update(
                twiml=recording_twiml
            )
            logger.info(f"Started recording for call {call_sid}")
            return {"status": "recording_started", "call_sid": call_sid}
        except Exception as twilio_error:
            logger.error(f"Could not start recording: {str(twilio_error)}")
            return {"status": "error", "message": str(twilio_error)}
            
    except Exception as e:
        logger.error(f"Error starting recording: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/transcriptions/recent")
async def get_recent_transcriptions(limit: int = Query(10, ge=1, le=100)):
    """Get recent transcriptions across all calls."""
    logger.info(f"Getting recent transcriptions with limit: {limit}")
    try:
        async with call_controller.prisma_service:
            # First try a simple count
            transcription_count = await call_controller.prisma_service.prisma.transcription.count()
            
            # Get transcriptions without complex includes first
            transcriptions = await call_controller.prisma_service.prisma.transcription.find_many(
                order={"timestamp": "desc"},
                take=limit
            )
            
            return {
                "total_transcriptions": transcription_count,
                "found_transcriptions": len(transcriptions),
                "transcriptions": [
                    {
                        "id": t.id,
                        "speaker": t.speaker,
                        "text": t.text,
                        "confidence": t.confidence,
                        "timestamp": t.timestamp.isoformat(),
                        "is_final": t.isFinal,
                        "session_id": t.sessionId,
                        "call_log_id": t.callLogId
                    }
                    for t in transcriptions
                ]
            }
    except Exception as e:
        logger.error(f"Error getting recent transcriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))