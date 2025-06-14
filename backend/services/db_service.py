from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

load_dotenv()

class DatabaseService:
    def __init__(self):
        self.client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
        self.db = self.client.voice_calling_db
        self.conversations = self.db.conversations
        self.users = self.db.users

    async def log_conversation(self, conversation_data: Dict[str, Any]) -> str:
        """
        Log a conversation in the database
        """
        try:
            conversation = {
                "call_sid": conversation_data.get("call_sid"),
                "contact_id": conversation_data.get("contact_id"),
                "start_time": datetime.now(),
                "end_time": None,
                "transcript": conversation_data.get("transcript", ""),
                "status": "in_progress",
                "metadata": conversation_data.get("metadata", {})
            }
            
            result = await self.conversations.insert_one(conversation)
            return str(result.inserted_id)
        except Exception as e:
            raise Exception(f"Failed to log conversation: {str(e)}")

    async def update_conversation(self, conversation_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update a conversation record
        """
        try:
            result = await self.conversations.update_one(
                {"_id": conversation_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            raise Exception(f"Failed to update conversation: {str(e)}")

    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID
        """
        try:
            conversation = await self.conversations.find_one({"_id": conversation_id})
            return conversation
        except Exception as e:
            raise Exception(f"Failed to get conversation: {str(e)}")

    async def store_user_data(self, user_data: Dict[str, Any]) -> str:
        """
        Store or update user data
        """
        try:
            user = {
                "phone_number": user_data.get("phone_number"),
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "last_contact": datetime.now(),
                "metadata": user_data.get("metadata", {})
            }
            
            result = await self.users.update_one(
                {"phone_number": user_data.get("phone_number")},
                {"$set": user},
                upsert=True
            )
            
            if result.upserted_id:
                return str(result.upserted_id)
            return str(result.modified_count)
        except Exception as e:
            raise Exception(f"Failed to store user data: {str(e)}")

    async def get_user_data(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Get user data by phone number
        """
        try:
            user = await self.users.find_one({"phone_number": phone_number})
            return user
        except Exception as e:
            raise Exception(f"Failed to get user data: {str(e)}")

    async def get_conversation_history(self, phone_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get conversation history for a user
        """
        try:
            cursor = self.conversations.find(
                {"contact_id": phone_number}
            ).sort("start_time", -1).limit(limit)
            
            conversations = await cursor.to_list(length=limit)
            return conversations
        except Exception as e:
            raise Exception(f"Failed to get conversation history: {str(e)}") 