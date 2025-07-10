import logging
from fastapi import HTTPException
from services.hubspot_service import HubspotService

logger = logging.getLogger(__name__)

class HubspotController:
    def __init__(self):
        self.hubspot_service = HubspotService()

    async def list_contacts(self, limit: int = 100):
        try:
            contacts = self.hubspot_service.get_contacts(limit=limit)
            return {"status": "success", "contacts": contacts}
        except Exception as e:
            logger.error(f"Error fetching contacts: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def update_contact_status(self, contact_id: str, status: str):
        try:
            self.hubspot_service.update_status(contact_id, status)
            return {"status": "success", "contact_id": contact_id, "new_status": status}
        except Exception as e:
            logger.error(f"Error updating contact status: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))