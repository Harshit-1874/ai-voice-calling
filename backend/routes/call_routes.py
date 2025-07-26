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

@router.get("/call/{phone_number}/context")
async def get_call_context(phone_number: str):
    """Get context information for a phone number before making a call."""
    logger.info("="*50)
    logger.info(f"Getting call context for phone number: {phone_number}")
    return await call_controller.get_call_context(phone_number)

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
    
    logger.info(f"TWiML endpoint called - CallSid: {call_sid}, From: {from_number}, To: {to_number}, Host: {ws_host}")
    logger.info(f"Form data received: {dict(form)}")
    
    twiml = twilio_service.create_twiml_response(
        ws_host=ws_host,
        from_number=from_number,
        to_number=to_number,
        call_sid=call_sid
    )
    
    logger.info(f"Generated TwiML for call {call_sid}: {twiml}")
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
        logger.info(f"WebSocket /media-stream handler received call_sid: {call_sid}")
        logger.info(f"WebSocket query parameters: {dict(websocket.query_params)}")
    else:
        logger.warning("WebSocket connected with no query parameters")
        # Try to extract call_sid from the first message if available
        logger.info("Will attempt to extract call_sid from first Twilio message")

    try:
        # Pass control directly to the WebSocketService's handler
        await websocket_service.handle_media_stream(websocket, call_sid)
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

@router.get("/transcriptions")
async def get_all_transcriptions():
    """Get all transcriptions (active and completed)."""
    try:
        transcription_service = websocket_service.get_transcription_service()
        transcriptions = transcription_service.get_all_transcriptions()
        
        # Convert to serializable format
        result = {}
        for call_sid, transcription in transcriptions.items():
            result[call_sid] = transcription.to_dict()
        
        return {
            "success": True,
            "transcriptions": result,
            "count": len(result)
        }
        
    except Exception as e:
        logger.error(f"Error getting all transcriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/transcriptions/{call_sid}")
async def get_call_transcription(call_sid: str):
    """Get transcription for a specific call."""
    try:
        transcription_service = websocket_service.get_transcription_service()
        transcription = transcription_service.get_call_transcription(call_sid)
        
        if not transcription:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        return {
            "success": True,
            "transcription": transcription.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcription for call {call_sid}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/transcriptions/{call_sid}/text")
async def get_call_transcription_text(
    call_sid: str, 
    include_timestamps: bool = Query(False, description="Include timestamps in the text")
):
    """Get transcription as formatted text."""
    try:
        transcription_service = websocket_service.get_transcription_service()
        text = transcription_service.get_transcription_text(call_sid, include_timestamps)
        
        if text is None:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        return Response(content=text, media_type="text/plain")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcription text for call {call_sid}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/transcriptions/{call_sid}/json")
async def get_call_transcription_json(call_sid: str):
    """Get transcription as JSON file."""
    try:
        transcription_service = websocket_service.get_transcription_service()
        json_data = transcription_service.export_transcription_json(call_sid)
        
        if json_data is None:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        return Response(
            content=json_data, 
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=transcription_{call_sid}.json"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting transcription JSON for call {call_sid}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transcriptions/{call_sid}/summary")
async def get_call_transcription_summary(call_sid: str):
    """Get a summary of the call transcription."""
    try:
        transcription_service = websocket_service.get_transcription_service()
        transcription = transcription_service.get_call_transcription(call_sid)
        
        if not transcription:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        # Calculate statistics
        total_entries = len(transcription.entries)
        final_entries = len([e for e in transcription.entries if e.is_final])
        user_entries = len([e for e in transcription.entries if e.speaker.value == "user" and e.is_final])
        assistant_entries = len([e for e in transcription.entries if e.speaker.value == "assistant" and e.is_final])
        
        # Calculate word counts
        user_words = sum(len(e.text.split()) for e in transcription.entries 
                        if e.speaker.value == "user" and e.is_final)
        assistant_words = sum(len(e.text.split()) for e in transcription.entries 
                             if e.speaker.value == "assistant" and e.is_final)
        
        # Calculate average confidence if available
        confidence_entries = [e for e in transcription.entries if e.confidence is not None and e.is_final]
        avg_confidence = (sum(e.confidence for e in confidence_entries) / len(confidence_entries)) if confidence_entries else None
        
        summary = {
            "call_sid": call_sid,
            "start_time": transcription.start_time.isoformat(),
            "end_time": transcription.end_time.isoformat() if transcription.end_time else None,
            "duration_seconds": transcription.total_duration,
            "is_active": call_sid in transcription_service.active_transcriptions,
            "statistics": {
                "total_entries": total_entries,
                "final_entries": final_entries,
                "user_entries": user_entries,
                "assistant_entries": assistant_entries,
                "user_words": user_words,
                "assistant_words": assistant_words,
                "total_words": user_words + assistant_words,
                "average_confidence": round(avg_confidence, 3) if avg_confidence else None
            }
        }
        
        return {
            "success": True,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcription summary for call {call_sid}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/transcriptions/{call_sid}")
async def delete_call_transcription(call_sid: str):
    """Delete a call transcription."""
    try:
        transcription_service = websocket_service.get_transcription_service()
        
        # Check if transcription exists
        transcription = transcription_service.get_call_transcription(call_sid)
        if not transcription:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        # Remove from completed transcriptions (don't delete active ones)
        if call_sid in transcription_service.completed_transcriptions:
            del transcription_service.completed_transcriptions[call_sid]
            logger.info(f"Deleted transcription for call {call_sid}")
            
            return {
                "success": True,
                "message": f"Transcription for call {call_sid} has been deleted"
            }
        else:
            raise HTTPException(status_code=400, detail="Cannot delete active transcription")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting transcription for call {call_sid}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    

