from fastapi import HTTPException, Request
import logging
from typing import Dict, Any
from services.twilio_service import TwilioService
from services.websocket_service import WebSocketService
from config import BASE_URL
import asyncio

logger = logging.getLogger(__name__)

class CallController:
    def __init__(self):
        self.twilio_service = TwilioService()
        self.websocket_service = WebSocketService()

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
            
            twiml = self.twilio_service.create_twiml_response(
                ws_host=ws_host,
                from_number=from_number,
                to_number=to_number
            )
            
            call_result = self.twilio_service.initiate_call(
                to_number=to_number,
                from_number=from_number,
                twiml=twiml
            )
            
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

    async def handle_incoming_call(self, request: Request) -> Dict[str, Any]:
        try:
            form_data = await request.form()
            logger.info(f"Incoming call form data: {form_data}")
            
            # Get host for WebSocket URL
            host = request.url.hostname
            logger.info(f"Using host for WebSocket: {host}")
            
            response = self.twilio_service.create_twiml_response(
                ws_host=host,
                from_number=form_data.get("From", ""),
                to_number=form_data.get("To", "")
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
            
            logger.info(f"Call {call_sid} status: {call_status}")
            
            if error_code:
                logger.error(f"Call error - Code: {error_code}, Message: {error_message}")
            
            return {"status": "success"}
            
        except Exception as e:
            logger.error(f"Error handling call status: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def poll_call_status(self, call_sid: str):
        """Poll the call status every 5 seconds"""
        logger.info(f"Starting status polling for call {call_sid}")
        try:
            while True:
                try:
                    call_status = self.twilio_service.get_call_status(call_sid)
                    logger.info(f"Call {call_sid} status: {call_status['status']}")
                    
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