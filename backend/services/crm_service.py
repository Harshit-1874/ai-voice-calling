from hubspot import HubSpot
from dotenv import load_dotenv
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

load_dotenv()

class CRMService:
    def __init__(self):
        self.client = HubSpot(access_token=os.getenv("HUBSPOT_API_KEY"))

    async def get_contacts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get contacts from HubSpot
        """
        try:
            contacts = self.client.crm.contacts.basic_api.get_page(limit=limit)
            return contacts.results
        except Exception as e:
            raise Exception(f"Failed to fetch contacts: {str(e)}")

    async def create_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new contact in HubSpot
        """
        try:
            contact = self.client.crm.contacts.basic_api.create(
                properties=contact_data
            )
            return contact
        except Exception as e:
            raise Exception(f"Failed to create contact: {str(e)}")

    async def update_contact(self, contact_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing contact in HubSpot
        """
        try:
            contact = self.client.crm.contacts.basic_api.update(
                contact_id=contact_id,
                properties=contact_data
            )
            return contact
        except Exception as e:
            raise Exception(f"Failed to update contact: {str(e)}")

    async def log_conversation(self, contact_id: str, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Log a conversation as a note in HubSpot
        """
        try:
            note_data = {
                "hs_timestamp": str(int(datetime.now().timestamp() * 1000)),
                "hs_note_body": conversation_data.get("transcript", ""),
                "hs_attachment_ids": "",
                "hubspot_owner_id": "",
                "hs_note_status": "DRAFT"
            }
            
            note = self.client.crm.objects.notes.basic_api.create(
                properties=note_data
            )
            
            # Associate note with contact
            self.client.crm.objects.notes.associations_api.create(
                note_id=note.id,
                to_object_type="contacts",
                to_object_id=contact_id,
                association_type="note_to_contact"
            )
            
            return note
        except Exception as e:
            raise Exception(f"Failed to log conversation: {str(e)}")

    async def mark_as_lead(self, contact_id: str, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mark a contact as a lead and update their properties
        """
        try:
            # Update contact properties
            contact_data = {
                "hs_lead_status": "NEW",
                "lead_source": lead_data.get("source", "AI Call"),
                "last_contact_date": datetime.now().isoformat(),
                "lead_notes": lead_data.get("notes", "")
            }
            
            contact = await self.update_contact(contact_id, contact_data)
            return contact
        except Exception as e:
            raise Exception(f"Failed to mark as lead: {str(e)}") 