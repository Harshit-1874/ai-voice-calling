import logging
from fastapi import HTTPException
from typing import Dict, List, Any, Optional
from services.prisma_service import PrismaService
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ContactCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

class ContactsController:
    def __init__(self):
        self.prisma_service = PrismaService()

    async def create_contact(self, contact_data: ContactCreate) -> Dict[str, Any]:
        """Create a new contact"""
        try:
            async with self.prisma_service:
                contact = await self.prisma_service.create_contact(
                    name=contact_data.name,
                    phone=contact_data.phone,
                    email=contact_data.email,
                    company=contact_data.company,
                    notes=contact_data.notes
                )
                
                return {
                    "id": contact.id,
                    "name": contact.name,
                    "phone": contact.phone,
                    "email": contact.email,
                    "company": contact.company,
                    "notes": contact.notes,
                    "created_at": contact.createdAt.isoformat(),
                    "updated_at": contact.updatedAt.isoformat()
                }
        except Exception as e:
            logger.error(f"Error creating contact: {str(e)}")
            if "UNIQUE constraint failed" in str(e):
                raise HTTPException(status_code=400, detail="Phone number already exists")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_contact(self, phone: str) -> Optional[Dict[str, Any]]:
        """Get contact by phone number"""
        try:
            async with self.prisma_service:
                contact = await self.prisma_service.get_contact_by_phone(phone)
                if not contact:
                    return None
                
                return {
                    "id": contact.id,
                    "name": contact.name,
                    "phone": contact.phone,
                    "email": contact.email,
                    "company": contact.company,
                    "notes": contact.notes,
                    "created_at": contact.createdAt.isoformat(),
                    "updated_at": contact.updatedAt.isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting contact: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_all_contacts(self) -> List[Dict[str, Any]]:
        """Get all contacts"""
        try:
            async with self.prisma_service:
                contacts = await self.prisma_service.get_all_contacts()
                
                return [
                    {
                        "id": contact.id,
                        "name": contact.name,
                        "phone": contact.phone,
                        "email": contact.email,
                        "company": contact.company,
                        "notes": contact.notes,
                        "created_at": contact.createdAt.isoformat(),
                        "updated_at": contact.updatedAt.isoformat()
                    }
                    for contact in contacts
                ]
        except Exception as e:
            logger.error(f"Error getting all contacts: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def update_contact(self, phone: str, contact_data: ContactUpdate) -> Dict[str, Any]:
        """Update contact by phone number"""
        try:
            async with self.prisma_service:
                # Check if contact exists
                existing_contact = await self.prisma_service.get_contact_by_phone(phone)
                if not existing_contact:
                    raise HTTPException(status_code=404, detail="Contact not found")
                
                # Prepare update data
                update_data = {}
                if contact_data.name is not None:
                    update_data["name"] = contact_data.name
                if contact_data.email is not None:
                    update_data["email"] = contact_data.email
                if contact_data.company is not None:
                    update_data["company"] = contact_data.company
                if contact_data.notes is not None:
                    update_data["notes"] = contact_data.notes
                
                contact = await self.prisma_service.update_contact(phone, **update_data)
                
                return {
                    "id": contact.id,
                    "name": contact.name,
                    "phone": contact.phone,
                    "email": contact.email,
                    "company": contact.company,
                    "notes": contact.notes,
                    "created_at": contact.createdAt.isoformat(),
                    "updated_at": contact.updatedAt.isoformat()
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating contact: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def delete_contact(self, phone: str) -> Dict[str, Any]:
        """Delete contact by phone number"""
        try:
            async with self.prisma_service:
                # Check if contact exists
                existing_contact = await self.prisma_service.get_contact_by_phone(phone)
                if not existing_contact:
                    raise HTTPException(status_code=404, detail="Contact not found")
                
                await self.prisma_service.delete_contact(phone)
                
                return {
                    "message": "Contact deleted successfully",
                    "phone": phone
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting contact: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_contact_with_calls(self, phone: str) -> Optional[Dict[str, Any]]:
        """Get contact with their call history"""
        try:
            async with self.prisma_service:
                contact = await self.prisma_service.get_contact_by_phone(phone)
                if not contact:
                    return None
                
                # Get call logs for this contact
                call_logs = await self.prisma_service.prisma.calllog.find_many({
                    'where': {'contactId': contact.id},
                    'order': {'startTime': 'desc'},
                    'include': {
                        'session': True,
                        'transcriptions': True
                    }
                })
                
                return {
                    "id": contact.id,
                    "name": contact.name,
                    "phone": contact.phone,
                    "email": contact.email,
                    "company": contact.company,
                    "notes": contact.notes,
                    "created_at": contact.createdAt.isoformat(),
                    "updated_at": contact.updatedAt.isoformat(),
                    "calls": [
                        {
                            "id": call.id,
                            "call_sid": call.callSid,
                            "from_number": call.fromNumber,
                            "to_number": call.toNumber,
                            "status": call.status,
                            "start_time": call.startTime.isoformat() if call.startTime else None,
                            "end_time": call.endTime.isoformat() if call.endTime else None,
                            "duration": call.duration,
                            "session": {
                                "id": call.session.id,
                                "session_id": call.session.sessionId,
                                "status": call.session.status,
                                "model": call.session.model,
                                "voice": call.session.voice
                            } if call.session else None,
                            "transcription_count": len(call.transcriptions)
                        }
                        for call in call_logs
                    ]
                }
        except Exception as e:
            logger.error(f"Error getting contact with calls: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e)) 