from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
import json
from typing import Dict, Any, Optional

load_dotenv()

class OpenAIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-realtime-preview-2024-12-17"  # Update with the latest model version

    async def create_realtime_session(self) -> Dict[str, Any]:
        """
        Create a new realtime session with OpenAI
        """
        try:
            response = await self.client.realtime.sessions.create(
                model=self.model,
                voice="alloy"  # You can change this to other available voices
            )
            return response
        except Exception as e:
            raise Exception(f"Failed to create OpenAI session: {str(e)}")

    async def process_audio_stream(self, audio_data: bytes, session_id: str) -> Dict[str, Any]:
        """
        Process incoming audio stream and get AI response
        """
        try:
            response = await self.client.realtime.audio.create(
                session_id=session_id,
                audio=audio_data
            )
            return response
        except Exception as e:
            raise Exception(f"Failed to process audio: {str(e)}")

    async def end_session(self, session_id: str) -> bool:
        """
        End the realtime session
        """
        try:
            await self.client.realtime.sessions.delete(session_id=session_id)
            return True
        except Exception as e:
            print(f"Error ending session: {str(e)}")
            return False

    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a realtime session
        """
        try:
            response = await self.client.realtime.sessions.retrieve(session_id=session_id)
            return response
        except Exception as e:
            print(f"Error getting session status: {str(e)}")
            return None 