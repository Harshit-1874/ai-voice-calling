import logging
from fastapi import APIRouter, WebSocket, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse
from controllers.call_controller import CallController
from services.websocket_service import WebSocketService
from services.twilio_service import TwilioService
import websockets
from fastapi.responses import Response
from datetime import datetime


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

@router.api_route("/incoming-call", methods=["POST"])
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

@router.post("/save-transcriptions/{call_sid}")
async def save_call_transcriptions(call_sid: str):
    """Manually save transcriptions for a specific call."""
    logger.info("="*50)
    logger.info(f"Manually saving transcriptions for call: {call_sid}")
    try:
        result = await call_controller.save_call_transcriptions(call_sid)
        return result
    except Exception as e:
        logger.error(f"Error saving transcriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/force-save-transcriptions/{call_sid}")
async def force_save_transcriptions(call_sid: str):
    """Force save transcriptions for a call, including any unmapped temp call_sids."""
    logger.info("="*50)
    logger.info(f"Force saving transcriptions for call: {call_sid}")
    try:
        # First, try to map any temp call_sids with transcriptions
        temp_call_sid = websocket_service.auto_map_temp_call_sids(call_sid)
        
        # Then finalize transcriptions
        await websocket_service.finalize_call_transcriptions(call_sid)
        
        # Check if any transcriptions were saved
        async with websocket_service.prisma_service:
            call_log = await websocket_service.prisma_service.get_call_log(call_sid)
            if call_log:
                transcriptions = await websocket_service.prisma_service.get_transcriptions_for_call(call_log.id)
                return {
                    "success": True,
                    "message": f"Force saved transcriptions for call {call_sid}",
                    "transcriptions_saved": len(transcriptions),
                    "temp_call_sid_mapped": temp_call_sid,
                    "buffer_state": {
                        "buffers": list(websocket_service.transcription_buffers.keys()),
                        "buffer_counts": {
                            k: v.get_transcription_count() 
                            for k, v in websocket_service.transcription_buffers.items()
                        }
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Call log not found"
                }
    except Exception as e:
        logger.error(f"Error force saving transcriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
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

    # Extract call_sid and to_number from query parameters
    call_sid = None
    to_number = None
    
    # Debug: Log all query parameters
    logger.info(f"WebSocket query parameters: {websocket.query_params}")
    logger.info(f"WebSocket URL: {websocket.url}")
    logger.info(f"WebSocket headers: {websocket.headers}")
    
    if websocket.query_params:
        call_sid = websocket.query_params.get("call_sid")
        to_number = websocket.query_params.get("to_number")
        logger.info(f"Call SID from query params: {call_sid}")
        logger.info(f"To number from query params: {to_number}")
    
    # If call_sid is not in query params, try to extract from URL path or headers
    if not call_sid:
        logger.warning("No call_sid found in query parameters, checking other sources...")
        # Check if call_sid is in the URL path or headers
        url_path = str(websocket.url)
        logger.info(f"Full WebSocket URL: {url_path}")
        
        # Try to extract call_sid from various sources
        if "call_sid=" in url_path:
            call_sid = url_path.split("call_sid=")[1].split("&")[0]
            logger.info(f"Extracted call_sid from URL: {call_sid}")
        
        # Check if call_sid is in headers
        if not call_sid:
            for header_name, header_value in websocket.headers.items():
                if "call" in header_name.lower() or "sid" in header_name.lower():
                    logger.info(f"Found potential call_sid in header {header_name}: {header_value}")
    
    if not call_sid:
        logger.error("No call_sid available for WebSocket connection!")
        # Try to get call_sid from the last active call or create a temporary one
        # This is a fallback for debugging
        call_sid = "temp_call_" + str(int(datetime.now().timestamp()))
        logger.warning(f"Using temporary call_sid: {call_sid}")
        
        # Try to find a pending call_sid that matches the to_number
        if to_number:
            logger.info(f"Looking for pending call_sid for to_number: {to_number}")
            logger.info(f"Available pending call_sids: {list(websocket_service.pending_call_sids.keys())}")
            for pending_call_sid, pending_info in websocket_service.pending_call_sids.items():
                logger.info(f"Checking pending call_sid {pending_call_sid}: {pending_info}")
                if pending_info.get("to_number") == to_number:
                    logger.info(f"Found pending call_sid {pending_call_sid} for to_number {to_number}")
                    # Map the temporary call_sid to the real call_sid
                    websocket_service.map_temp_to_real_call_sid(call_sid, pending_call_sid)
                    call_sid = pending_call_sid
                    logger.info(f"Mapped temporary call_sid to real call_sid: {call_sid}")
                    break
            else:
                logger.warning(f"No pending call_sid found for to_number {to_number}")
        else:
            logger.warning("No to_number available for call_sid mapping")
    
    # If we have a temp call_sid, try to map it to a real call_sid
    if call_sid and call_sid.startswith("temp_call_"):
        logger.info(f"WebSocket using temp call_sid: {call_sid}")
        # Try to find a pending call_sid to map to
        if websocket_service.pending_call_sids:
            # Get the most recent pending call_sid
            most_recent_call_sid = max(
                websocket_service.pending_call_sids.keys(),
                key=lambda x: websocket_service.pending_call_sids[x].get("created_at", datetime.min)
            )
            logger.info(f"Mapping temp call_sid {call_sid} to most recent pending call_sid {most_recent_call_sid}")
            websocket_service.map_temp_to_real_call_sid(call_sid, most_recent_call_sid)
            call_sid = most_recent_call_sid
            logger.info(f"Now using real call_sid: {call_sid}")
        else:
            logger.warning(f"No pending call_sids available to map temp call_sid {call_sid}")
            # Try to find any real call_sid that might match
            # This is a fallback for when the WebSocket connects after the call is already created
            try:
                async with websocket_service.prisma_service:
                    # Get the most recent call log
                    call_logs = await websocket_service.prisma_service.get_all_call_logs(limit=1)
                    if call_logs:
                        most_recent_call_sid = call_logs[0].callSid
                        logger.info(f"Mapping temp call_sid {call_sid} to most recent call_sid from DB: {most_recent_call_sid}")
                        websocket_service.map_temp_to_real_call_sid(call_sid, most_recent_call_sid)
                        call_sid = most_recent_call_sid
                        logger.info(f"Now using real call_sid from DB: {call_sid}")
            except Exception as e:
                logger.error(f"Error mapping temp call_sid to DB call_sid: {str(e)}")
    
    # If we still don't have a valid call_sid, try to get the most recent call from database
    if not call_sid or call_sid.startswith("temp_call_"):
        try:
            async with websocket_service.prisma_service:
                # Get the most recent call log
                call_logs = await websocket_service.prisma_service.get_all_call_logs(limit=1)
                if call_logs:
                    call_sid = call_logs[0].callSid
                    logger.info(f"Using most recent call_sid from database: {call_sid}")
        except Exception as e:
            logger.error(f"Error getting most recent call from database: {str(e)}")

    try:
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            extra_headers={
                "Authorization": f"Bearer {websocket_service.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            logger.info("Connected to OpenAI WebSocket")
            logger.info(f"Initializing session with call_sid: {call_sid}, to_number: {to_number}")
            await websocket_service.initialize_session(openai_ws, call_sid, to_number)
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

@router.post("/debug-transcription/{call_sid}")
async def debug_transcription(call_sid: str):
    """Debug transcription processing for a specific call."""
    logger.info("="*50)
    logger.info(f"Debugging transcription for: {call_sid}")
    try:
        # Check transcription status
        transcription_service = websocket_service.get_transcription_service()
        memory_transcription = transcription_service.get_call_transcription(call_sid)
        
        # Check buffer
        buffer_transcriptions = 0
        buffer_details = []
        if call_sid in websocket_service.transcription_buffers:
            buffer = websocket_service.transcription_buffers[call_sid]
            buffer_transcriptions = buffer.get_transcription_count()
            buffer_details = [
                {
                    "speaker": t["speaker"],
                    "text": t["text"][:100],
                    "confidence": t.get("confidence"),
                    "timestamp": t["timestamp"].isoformat() if t["timestamp"] else None
                }
                for t in buffer.transcriptions
            ]
        
        # Check database
        async with websocket_service.prisma_service:
            call_log = await websocket_service.prisma_service.get_call_log(call_sid)
            db_transcriptions = []
            if call_log:
                db_transcriptions = await websocket_service.prisma_service.get_transcriptions_for_call(call_log.id)
        
        debug_info = {
            "call_sid": call_sid,
            "memory_transcription": memory_transcription is not None,
            "memory_entries": len(memory_transcription.entries) if memory_transcription else 0,
            "buffer_transcriptions": buffer_transcriptions,
            "buffer_details": buffer_details,
            "database_transcriptions": len(db_transcriptions),
            "call_log_exists": call_log is not None,
            "active_transcriptions": list(transcription_service.active_transcriptions.keys()),
            "completed_transcriptions": list(transcription_service.completed_transcriptions.keys()),
            "buffer_keys": list(websocket_service.transcription_buffers.keys())
        }
        
        return {
            "success": True,
            "debug_info": debug_info
        }
    except Exception as e:
        logger.error(f"Error debugging transcription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-transcription-buffer/{call_sid}")
async def test_transcription_buffer(call_sid: str):
    """Test adding a transcription to the buffer."""
    logger.info("="*50)
    logger.info(f"Testing transcription buffer for: {call_sid}")
    try:
        # Get or create buffer
        buffer = websocket_service.get_or_create_transcription_buffer(call_sid)
        
        # Add a test transcription
        buffer.add_transcription(
            speaker="user",
            text="This is a test transcription",
            confidence=0.95
        )
        
        # Add another test transcription
        buffer.add_transcription(
            speaker="assistant",
            text="This is a test response",
            confidence=0.98
        )
        
        return {
            "success": True,
            "message": f"Added test transcriptions to buffer for call {call_sid}",
            "buffer_count": buffer.get_transcription_count(),
            "buffer_transcriptions": [
                {
                    "speaker": t["speaker"],
                    "text": t["text"],
                    "confidence": t.get("confidence")
                }
                for t in buffer.transcriptions
            ]
        }
    except Exception as e:
        logger.error(f"Error testing transcription buffer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/map-call-sid")
async def map_call_sid(temp_call_sid: str, real_call_sid: str):
    """Map a temporary call_sid to a real call_sid for transcription tracking."""
    logger.info("="*50)
    logger.info(f"Mapping call_sid: {temp_call_sid} -> {real_call_sid}")
    try:
        websocket_service.map_temp_to_real_call_sid(temp_call_sid, real_call_sid)
        
        # Check if transcriptions exist for the temp call_sid
        buffer_count = 0
        if temp_call_sid in websocket_service.transcription_buffers:
            buffer_count = websocket_service.transcription_buffers[temp_call_sid].get_transcription_count()
        
        active_count = 0
        if temp_call_sid in websocket_service.transcription_service.active_transcriptions:
            active_count = len(websocket_service.transcription_service.active_transcriptions[temp_call_sid].entries)
        
        completed_count = 0
        if temp_call_sid in websocket_service.transcription_service.completed_transcriptions:
            completed_count = len(websocket_service.transcription_service.completed_transcriptions[temp_call_sid].entries)
        
        return {
            "success": True,
            "message": f"Mapped {temp_call_sid} to {real_call_sid}",
            "temp_call_sid": temp_call_sid,
            "real_call_sid": real_call_sid,
            "transcriptions_found": {
                "buffer": buffer_count,
                "active": active_count,
                "completed": completed_count
            }
        }
    except Exception as e:
        logger.error(f"Error mapping call_sid: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auto-map-call/{real_call_sid}")
async def auto_map_call(real_call_sid: str):
    """Automatically map any temp call_sid with transcriptions to the real call_sid."""
    logger.info("="*50)
    logger.info(f"Auto-mapping temp call_sids to real call_sid: {real_call_sid}")
    try:
        temp_call_sid = websocket_service.auto_map_temp_call_sids(real_call_sid)
        if temp_call_sid:
            return {
                "success": True,
                "message": f"Auto-mapped {temp_call_sid} to {real_call_sid}",
                "temp_call_sid": temp_call_sid,
                "real_call_sid": real_call_sid
            }
        else:
            return {
                "success": False,
                "message": f"No temp call_sid with transcriptions found to map to {real_call_sid}"
            }
    except Exception as e:
        logger.error(f"Error auto-mapping call_sid: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/call-context/{phone_number}")
async def get_call_context(phone_number: str, limit: int = Query(3, ge=1, le=10)):
    """Get previous call context for a phone number."""
    logger.info("="*50)
    logger.info(f"Getting call context for: {phone_number}")
    try:
        context = await call_controller.get_previous_call_context(phone_number, limit)
        return {
            "success": True,
            "phone_number": phone_number,
            "context": context,
            "has_context": bool(context.strip())
        }
    except Exception as e:
        logger.error(f"Error getting call context: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/call-confidence/{call_sid}")
async def get_call_confidence(call_sid: str):
    """Get confidence scores for a call's transcriptions."""
    logger.info("="*50)
    logger.info(f"Getting confidence scores for: {call_sid}")
    try:
        confidence_scores = await websocket_service.transcription_service.get_call_confidence_score(call_sid)
        return {
            "success": True,
            "call_sid": call_sid,
            "confidence_scores": confidence_scores
        }
    except Exception as e:
        logger.error(f"Error getting confidence scores: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transcription-status/{call_sid}")
async def get_transcription_status(call_sid: str):
    """Get transcription status for a specific call."""
    logger.info("="*50)
    logger.info(f"Getting transcription status for: {call_sid}")
    try:
        # Check if transcription exists in memory
        transcription_service = websocket_service.get_transcription_service()
        memory_transcription = transcription_service.get_call_transcription(call_sid)
        
        # Check if transcription exists in database
        async with websocket_service.prisma_service:
            call_log = await websocket_service.prisma_service.get_call_log(call_sid)
            db_transcriptions = []
            if call_log:
                db_transcriptions = await websocket_service.prisma_service.get_transcriptions_for_call(call_log.id)
        
        # Check buffer status
        buffer_transcriptions = 0
        if call_sid in websocket_service.transcription_buffers:
            buffer_transcriptions = websocket_service.transcription_buffers[call_sid].get_transcription_count()
        
        status = {
            "call_sid": call_sid,
            "in_memory": memory_transcription is not None,
            "in_database": len(db_transcriptions) > 0,
            "in_buffer": buffer_transcriptions > 0,
            "memory_entries": len(memory_transcription.entries) if memory_transcription else 0,
            "database_entries": len(db_transcriptions),
            "buffer_entries": buffer_transcriptions,
            "call_log_exists": call_log is not None,
            "active_transcriptions": list(websocket_service.transcription_service.active_transcriptions.keys()),
            "completed_transcriptions": list(websocket_service.transcription_service.completed_transcriptions.keys()),
            "buffer_keys": list(websocket_service.transcription_buffers.keys())
        }
        
        return {
            "success": True,
            "status": status
        }
    except Exception as e:
        logger.error(f"Error getting transcription status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/debug-state")
async def debug_state():
    """Get the current state of all mappings, buffers, and transcriptions for debugging."""
    logger.info("="*50)
    logger.info("Getting debug state")
    try:
        # Get all the current state
        state = {
            "temp_to_real_mapping": websocket_service.temp_to_real_call_mapping,
            "session_to_call_mapping": websocket_service.session_to_call_mapping,
            "pending_call_sids": websocket_service.pending_call_sids,
            "transcription_buffers": {
                call_sid: {
                    "count": buffer.get_transcription_count(),
                    "transcriptions": [
                        {
                            "speaker": t["speaker"],
                            "text": t["text"][:50] + "...",
                            "confidence": t.get("confidence")
                        }
                        for t in buffer.transcriptions[:3]  # Show first 3
                    ]
                }
                for call_sid, buffer in websocket_service.transcription_buffers.items()
            },
            "active_transcriptions": list(websocket_service.transcription_service.active_transcriptions.keys()),
            "completed_transcriptions": list(websocket_service.transcription_service.completed_transcriptions.keys()),
            "temp_call_sids_with_transcriptions": [
                call_sid for call_sid, buffer in websocket_service.transcription_buffers.items()
                if call_sid.startswith("temp_call_") and buffer.get_transcription_count() > 0
            ],
            "real_call_sids_with_transcriptions": [
                call_sid for call_sid, buffer in websocket_service.transcription_buffers.items()
                if not call_sid.startswith("temp_call_") and buffer.get_transcription_count() > 0
            ]
        }
        
        # Also get recent call logs from database
        try:
            async with websocket_service.prisma_service:
                recent_calls = await websocket_service.prisma_service.get_all_call_logs(limit=5)
                state["recent_call_logs"] = [
                    {
                        "call_sid": call.callSid,
                        "status": call.status,
                        "from_number": call.fromNumber,
                        "to_number": call.toNumber,
                        "start_time": call.startTime.isoformat() if call.startTime else None
                    }
                    for call in recent_calls
                ]
        except Exception as db_error:
            logger.error(f"Error getting recent call logs: {str(db_error)}")
            state["recent_call_logs"] = []
        
        return {
            "success": True,
            "state": state
        }
    except Exception as e:
        logger.error(f"Error getting debug state: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-openai-connection")
async def test_openai_connection():
    """Test OpenAI WebSocket connection and session setup."""
    logger.info("="*50)
    logger.info("Testing OpenAI connection")
    try:
        import websockets
        import json
        
        # Test connection to OpenAI
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            extra_headers={
                "Authorization": f"Bearer {websocket_service.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            logger.info("Successfully connected to OpenAI WebSocket")
            
            # Test session update
            session_update = {
                "type": "session.update",
                "session": {
                    "turn_detection": {"type": "server_vad","threshold": 0.5},
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": "echo",
                    "instructions": "You are a test assistant.",
                    "modalities": ["text", "audio"],
                    "temperature": 0.7,
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    }
                }
            }
            
            logger.info("Sending test session update")
            await openai_ws.send(json.dumps(session_update))
            
            # Wait for response
            response = await openai_ws.recv()
            response_data = json.loads(response)
            logger.info(f"Received response: {response_data}")
            
            return {
                "success": True,
                "message": "OpenAI connection test successful",
                "response": response_data
            }
            
    except Exception as e:
        logger.error(f"Error testing OpenAI connection: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
    

