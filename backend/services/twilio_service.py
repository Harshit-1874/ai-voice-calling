import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.client = Client(self.account_sid, self.auth_token)
    
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
        except TwilioRestException as e:
            logger.error(f"Twilio API error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_call_status(self, call_sid: str) -> dict:
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                "success": True,
                "status": call.status,
                "duration": call.duration
            }
        except TwilioRestException as e:
            logger.error(f"Twilio API error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            } 