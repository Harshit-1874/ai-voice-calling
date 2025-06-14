from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv
import os
from typing import Optional

load_dotenv()

class TwilioService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.client = Client(self.account_sid, self.auth_token)
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")

    async def make_call(self, to_number: str, webhook_url: str) -> str:
        """
        Initiate an outbound call using Twilio
        """
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=webhook_url,
                status_callback=webhook_url + "/status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed']
            )
            return call.sid
        except Exception as e:
            raise Exception(f"Failed to initiate call: {str(e)}")

    def generate_twiml(self, websocket_url: str) -> str:
        """
        Generate TwiML for connecting to WebSocket
        """
        response = VoiceResponse()
        connect = Connect()
        connect.stream(url=websocket_url)
        response.append(connect)
        return str(response)

    async def get_call_status(self, call_sid: str) -> Optional[str]:
        """
        Get the status of a call
        """
        try:
            call = self.client.calls(call_sid).fetch()
            return call.status
        except Exception as e:
            print(f"Error getting call status: {str(e)}")
            return None

    async def end_call(self, call_sid: str) -> bool:
        """
        End an active call
        """
        try:
            self.client.calls(call_sid).update(status="completed")
            return True
        except Exception as e:
            print(f"Error ending call: {str(e)}")
            return False 