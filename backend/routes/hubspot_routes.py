import logging
from fastapi import APIRouter, HTTPException
from typing import List
from controllers.hubspot_controller import HubspotController

logger = logging.getLogger(__name__)
router = APIRouter()
hubspot_controller = HubspotController()

@router.get("/hubspot/contacts")
async def list_contacts():
    """Get all contacts from HubSpot."""
    return await hubspot_controller.list_contacts()