from fastapi import HTTPException, Request
import logging
from typing import Dict, Any
from services.twilio_service import TwilioService
from services.websocket_service import WebSocketService
from services.prisma_service import PrismaService
from services.context_service import ContextService
from config import BASE_URL
import asyncio
import json

logger = logging.getLogger(__name__)

class CallController:
    def __init__(self):
        self.twilio_service = TwilioService()
        self.websocket_service = WebSocketService()
        self.prisma_service = PrismaService()
        self.context_service = ContextService()

    async def initiate_call(self, phone_number: str, request: Request) -> Dict[str, Any]:
        try:
            if not phone_number:
                raise HTTPException(status_code=400, detail="Phone number is required")
                
            to_number = self.twilio_service.clean_phone_number(phone_number)
            if not to_number:
                raise HTTPException(status_code=400, detail="Invalid phone number format")
                
            from_number = self.twilio_service.clean_phone_number(self.twilio_service.phone_number)
            
            # Get base URL and host
            base_url = BASE_URL.rstrip('/')
            # Use the ngrok URL for WebSocket
            ws_host = base_url.replace('https://', '').replace('http://', '')
            logger.info(f"Using base URL: {base_url}")
            logger.info(f"Using WebSocket host: {ws_host}")
            
            # First create the call to get the call_sid
            call_result = self.twilio_service.initiate_call(
                to_number=to_number,
                from_number=from_number,
                twiml="<Response><Say>Please wait while we connect your call.</Say></Response>"
            )
            
            # Store call log in database immediately
            async with self.prisma_service:
                try:
                    await self.prisma_service.create_call_log(
                        call_sid=call_result["call_sid"],
                        from_number=from_number,
                        to_number=to_number,
                        status="initiated"
                    )
                    logger.info(f"Call log created for {call_result['call_sid']}")
                except Exception as db_error:
                    logger.warning(f"Could not create call log: {str(db_error)}")
            
            # Now create the proper TwiML with the call_sid
            logger.info(f"Creating TwiML for call_sid: {call_result['call_sid']}")
            twiml = self.twilio_service.create_twiml_response(
                ws_host=ws_host,
                from_number=from_number,
                to_number=to_number,
                call_sid=call_result["call_sid"]
            )
            
            # Update the call with the proper TwiML
            try:
                logger.info(f"Updating call {call_result['call_sid']} with new TwiML")
                self.twilio_service.client.calls(call_result["call_sid"]).update(twiml=twiml)
                logger.info(f"Successfully updated call {call_result['call_sid']} with TwiML")
                logger.info(f"TWiML content: {twiml}")
            except Exception as twilio_error:
                logger.error(f"Could not update call with TwiML: {str(twilio_error)}")
                logger.error(f"Call SID: {call_result['call_sid']}")
                logger.error(f"TWiML that failed: {twiml}")
            
            asyncio.create_task(self.poll_call_status(call_result["call_sid"]))
            
            return {
                "message": "Call initiated",
                "call_sid": call_result["call_sid"],
                "to": to_number,
                "from": from_number,
                "status": "initiated",
                "twiml": twiml
            }
            
        except Exception as e:
            logger.error(f"Error initiating call: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_call_context(self, phone_number: str) -> Dict[str, Any]:
        """Get context information for a phone number before making a call"""
        try:
            cleaned_number = self.twilio_service.clean_phone_number(phone_number)
            if not cleaned_number:
                raise HTTPException(status_code=400, detail="Invalid phone number format")
            
            async with self.prisma_service:
                # Get call history and context
                call_context = await self.prisma_service.get_contact_context_by_phone(cleaned_number)
                
                if not call_context or not call_context.get('call_history'):
                    return {
                        "phone_number": cleaned_number,
                        "has_previous_calls": False,
                        "message": "No previous call history found. This will be a first-time call."
                    }
                
                # Extract context from call history
                context = self.context_service.extract_context_from_call_history(call_context['call_history'])
                
                # Format response with context information
                response = {
                    "phone_number": cleaned_number,
                    "has_previous_calls": True,
                    "total_previous_calls": context.get('total_calls', 0),
                    "last_call_date": context.get('last_call_date'),
                    "customer_name": context.get('customer_name'),
                    "business_name": context.get('business_name'),
                    "business_type": context.get('business_type'),
                    "payment_preferences": context.get('payment_preferences', []),
                    "previous_interests": context.get('previous_interests', []),
                    "previous_objections": context.get('previous_objections', []),
                    "call_outcomes": context.get('call_outcomes', []),
                    "key_insights": context.get('key_insights', []),
                    "last_conversation_summary": context.get('last_conversation_summary'),
                    "contact_info": call_context.get('contact')
                }
                
                # Generate a human-readable summary
                summary_parts = []
                if context.get('customer_name'):
                    summary_parts.append(f"Customer name: {context['customer_name']}")
                if context.get('business_name'):
                    summary_parts.append(f"Business: {context['business_name']}")
                elif context.get('business_type'):
                    summary_parts.append(f"Business type: {context['business_type']}")
                if context.get('total_calls'):
                    summary_parts.append(f"Previous calls: {context['total_calls']}")
                if context.get('previous_objections'):
                    summary_parts.append(f"Previous concerns: {', '.join(context['previous_objections'][:2])}")
                
                response["summary"] = "; ".join(summary_parts) if summary_parts else "Previous call history available"
                
                return response
                
        except Exception as e:
            logger.error(f"Error getting call context for {phone_number}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def handle_incoming_call(self, request: Request) -> Dict[str, Any]:
        try:
            form_data = await request.form()
            logger.info(f"Incoming call form data: {form_data}")
            
            # Get host for WebSocket URL
            host = request.url.hostname
            call_sid = form_data.get("CallSid")
            logger.info(f"Using host for WebSocket: {host}")
            logger.info(f"Incoming call CallSid: {call_sid}")
            
            response = self.twilio_service.create_twiml_response(
                ws_host=host,
                from_number=form_data.get("From", ""),
                to_number=form_data.get("To", ""),
                call_sid=call_sid
            )
            
            return {"twiml": response}
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def handle_call_status(self, request: Request) -> Dict[str, Any]:
        try:
            form_data = await request.form()
            call_sid = form_data.get("CallSid")
            call_status = form_data.get("CallStatus")
            from_number = form_data.get("From")
            to_number = form_data.get("To")
            error_code = form_data.get("ErrorCode")
            error_message = form_data.get("ErrorMessage")
            call_duration = form_data.get("CallDuration")
            recording_url = form_data.get("RecordingUrl")
            logger.info(f"Call {call_sid} status: {call_status}")
            if error_code:
                logger.error(f"Call error - Code: {error_code}, Message: {error_message}")
            # Update call log in database
            try:
                async with self.prisma_service:
                    result = await self.prisma_service.update_call_status(
                        call_sid=call_sid,
                        status=call_status,
                        duration=int(call_duration) if call_duration else None,
                        error_code=error_code,
                        error_message=error_message,
                        recording_url=recording_url
                    )
                    if result:
                        logger.info(f"Successfully updated call status for {call_sid}")
                    else:
                        logger.warning(f"Database update returned None for {call_sid}")
            except Exception as db_error:
                logger.error(f"Database error in handle_call_status: {str(db_error)}")
                # Don't fail the request, just log the error

            # Flush transcription buffer if call is finished
            if call_status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
                logger.info(f"Call {call_sid} ended with status: {call_status}. Triggering transcription finalization.")
                try:
                    await self.websocket_service.finalize_call_transcriptions(call_sid)
                except Exception as flush_error:
                    logger.error(f"Error finalizing transcriptions for call {call_sid}: {flush_error}")

            # Always return 200 OK to Twilio, even if there was an error
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error handling call status: {str(e)}")
            # Always return 200 OK to Twilio, even if there was an error
            return {"status": "success"}

    async def poll_call_status(self, call_sid: str):
        """Poll the call status every 5 seconds"""
        logger.info(f"Starting status polling for call {call_sid}")
        try:
            while True:
                try:
                    call_status = self.twilio_service.get_call_status(call_sid)
                    logger.info(f"Call {call_sid} status: {call_status['status']}")
                    
                    # Update database with current status
                    try:
                        async with self.prisma_service:
                            result = await self.prisma_service.update_call_status(
                                call_sid=call_sid,
                                status=call_status['status'],
                                error_code=call_status.get('error_code'),
                                error_message=call_status.get('error_message')
                            )
                            if result:
                                logger.debug(f"Updated call status in database for {call_sid}")
                            else:
                                logger.warning(f"Database update failed for {call_sid}")
                    except Exception as db_error:
                        logger.error(f"Database error in poll_call_status: {str(db_error)}")
                        # Continue polling even if database fails
                    
                    if call_status['status'] in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
                        logger.info(f"Call {call_sid} ended with status: {call_status['status']}")
                        if call_status['status'] == 'failed':
                            logger.error(f"Call failed - Error Code: {call_status.get('error_code')}, Error Message: {call_status.get('error_message')}")
                        break
                    
                    await asyncio.sleep(5)  # Poll every 5 seconds
                    
                except Exception as poll_error:
                    logger.error(f"Error polling call status: {str(poll_error)}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in poll_call_status: {str(e)}")

    async def get_call_logs(self, limit: int = 100) -> Dict[str, Any]:
        """Get all call logs"""
        try:
            async with self.prisma_service:
                call_logs = await self.prisma_service.get_all_call_logs(limit=limit)
                stats = await self.prisma_service.get_call_statistics()
                
                return {
                    "call_logs": [
                        {
                            "id": log.id,
                            "call_sid": log.callSid,
                            "from_number": log.fromNumber,
                            "to_number": log.toNumber,
                            "status": log.status,
                            "start_time": log.startTime.isoformat() if log.startTime else None,
                            "end_time": log.endTime.isoformat() if log.endTime else None,
                            "duration": log.duration,
                            "contact": {
                                "id": log.contact.id,
                                "name": log.contact.name,
                                "phone": log.contact.phone
                            } if log.contact else None
                        }
                        for log in call_logs
                    ],
                    "statistics": stats
                }
        except Exception as e:
            logger.error(f"Error getting call logs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_call_details(self, call_sid: str) -> Dict[str, Any]:
        """Get detailed call information including transcriptions"""
        try:
            async with self.prisma_service:
                call_log = await self.prisma_service.get_call_log(call_sid)
                if not call_log:
                    raise HTTPException(status_code=404, detail="Call not found")
                
                transcriptions = await self.prisma_service.get_transcriptions_for_call(call_log.id)
                conversation = await self.prisma_service.get_conversation_analysis(call_log.id)
                
                return {
                    "call": {
                        "id": call_log.id,
                        "call_sid": call_log.callSid,
                        "from_number": call_log.fromNumber,
                        "to_number": call_log.toNumber,
                        "status": call_log.status,
                        "start_time": call_log.startTime.isoformat() if call_log.startTime else None,
                        "end_time": call_log.endTime.isoformat() if call_log.endTime else None,
                        "duration": call_log.duration,
                        "error_code": call_log.errorCode,
                        "error_message": call_log.errorMessage,
                        "recording_url": call_log.recordingUrl,
                        "contact": {
                            "id": call_log.contact.id,
                            "name": call_log.contact.name,
                            "phone": call_log.contact.phone
                        } if call_log.contact else None,
                        "session": {
                            "id": call_log.session.id,
                            "session_id": call_log.session.sessionId,
                            "status": call_log.session.status,
                            "model": call_log.session.model,
                            "voice": call_log.session.voice
                        } if call_log.session else None
                    },
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
                    ],
                    "conversation_analysis": {
                        "summary": conversation.summary,
                        "key_points": json.loads(conversation.keyPoints) if conversation and conversation.keyPoints else None,
                        "sentiment": conversation.sentiment,
                        "lead_score": conversation.leadScore,
                        "next_action": conversation.nextAction
                    } if conversation else None
                }
        except Exception as e:
            logger.error(f"Error getting call details: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e)) 