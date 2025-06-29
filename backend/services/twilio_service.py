import os
import logging
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream, Record
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, BASE_URL
from fastapi.responses import Response

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise ValueError("Twilio credentials not found in environment variables")
            
        self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        self.phone_number = TWILIO_PHONE_NUMBER
        logger.info("TwilioService initialized")

    def clean_phone_number(self, number: str) -> str:
        """Clean and format phone number."""
        logger.debug(f"Cleaning phone number: {number}")
        cleaned = ''.join(c for c in number if c.isdigit() or c == '+')
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        logger.debug(f"Cleaned phone number: {cleaned}")
        return cleaned

    def create_twiml_response(self, ws_host: str, from_number: str, to_number: str, call_sid: str = None) -> str:
        """Create TwiML response for the call with WebSocket streaming AND recording/transcription."""
        try:
            response = VoiceResponse()
            
            # Add initial greeting
            response.say("Please wait while we connect your call to the AI voice assistant.")
            response.pause(length=1)
            
            # Setup WebSocket connection for real-time AI conversation
            connect = Connect()
            stream_url = f'wss://{ws_host}/media-stream'
            if call_sid:
                stream_url += f'?call_sid={call_sid}'
            logger.info(f"WebSocket stream URL: {stream_url}")
            
            # Configure stream with parameters
            stream = Stream(url=stream_url)
            stream.parameter(name="From", value=from_number)
            stream.parameter(name="To", value=to_number)
            if call_sid:
                stream.parameter(name="CallSid", value=call_sid)
            connect.append(stream)
            response.append(connect)
            
            # ALSO start recording with transcription for backup/compliance
            # This runs in parallel with the WebSocket stream
            recording_callback_url = f"{BASE_URL.rstrip('/')}/recording-callback"
            transcription_callback_url = f"{BASE_URL.rstrip('/')}/transcription-callback"
            
            # Start recording
            response.record(
                action=recording_callback_url,
                method="POST",
                timeout=3600,  # Long timeout to capture entire call
                max_length=7200,  # 2 hours max
                transcribe=True,  # Enable transcription
                transcribe_callback=transcription_callback_url,
                play_beep=False,  # Don't play beep when recording starts
                trim="trim-silence"  # Remove silence from beginning and end
            )
            
            # Add final instruction
            response.say("You can start talking now!")
            
            twiml = str(response)
            logger.info(f"Generated TwiML with WebSocket connection AND recording: {twiml}")
            return twiml
            
        except Exception as e:
            logger.error(f"Error creating TwiML response: {str(e)}")
            raise

    def create_recording_twiml_response(self, call_sid: str = None) -> str:
        """Create separate TwiML response for recording (if needed)."""
        try:
            response = VoiceResponse()
            
            # Start recording with transcription
            recording_callback_url = f"{BASE_URL.rstrip('/')}/recording-callback"
            response.record(
                action=recording_callback_url,
                method="POST",
                timeout=3600,  # Long timeout to capture entire call
                max_length=7200,  # 2 hours max
                transcribe=True,  # Enable transcription
                transcribe_callback=f"{BASE_URL.rstrip('/')}/transcription-callback",
                play_beep=False,  # Don't play beep when recording starts
                trim="trim-silence"  # Remove silence from beginning and end
            )
            
            twiml = str(response)
            logger.info(f"Generated recording TwiML: {twiml}")
            return twiml
            
        except Exception as e:
            logger.error(f"Error creating recording TwiML response: {str(e)}")
            raise

    def initiate_call(self, to_number: str, from_number: str, twiml: str) -> dict:
        """Initiate a call using Twilio."""
        try:
            logger.info(f"Initiating call from {from_number} to {to_number}")
            
            # Make the call with TwiML
            call = self.client.calls.create(
                to=to_number,
                from_=from_number,
                url=f"{BASE_URL.rstrip('/')}/twiml",
                status_callback=f"{BASE_URL.rstrip('/')}/call-status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed']
            )
            
            logger.info(f"Call created successfully with SID: {call.sid}")
            return {
                "call_sid": call.sid,
                "status": call.status
            }
            
        except Exception as e:
            logger.error(f"Error initiating call: {str(e)}")
            raise

    def get_call_status(self, call_sid: str) -> dict:
        """Get the status of a call."""
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                "status": call.status,
                "from_number": getattr(call, 'from_', None) or getattr(call, 'from', None),
                "to_number": getattr(call, 'to', None),
                "error_code": getattr(call, 'error_code', None),
                "error_message": getattr(call, 'error_message', None)
            }
        except Exception as e:
            logger.error(f"Error getting call status: {str(e)}")
            raise

    def make_call(self, to_number: str, webhook_url: str) -> dict:
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=webhook_url
            )
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            } 