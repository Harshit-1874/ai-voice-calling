import logging
from fastapi import APIRouter, HTTPException
from typing import List
from controllers.contacts_controller import ContactsController, ContactCreate, ContactUpdate

logger = logging.getLogger(__name__)
router = APIRouter()
contacts_controller = ContactsController()

@router.post("/contacts")
async def create_contact(contact_data: ContactCreate):
    """Create a new contact."""
    logger.info("="*50)
    logger.info(f"Creating contact: {contact_data.name} ({contact_data.phone})")
    return await contacts_controller.create_contact(contact_data)

@router.get("/contacts")
async def get_all_contacts():
    """Get all contacts."""
    logger.info("="*50)
    logger.info("Getting all contacts")
    return await contacts_controller.get_all_contacts()

@router.get("/contacts/{phone}")
async def get_contact(phone: str):
    """Get contact by phone number."""
    logger.info("="*50)
    logger.info(f"Getting contact: {phone}")
    contact = await contacts_controller.get_contact(phone)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.get("/contacts/{phone}/calls")
async def get_contact_with_calls(phone: str):
    """Get contact with their call history."""
    logger.info("="*50)
    logger.info(f"Getting contact with calls: {phone}")
    contact = await contacts_controller.get_contact_with_calls(phone)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.put("/contacts/{phone}")
async def update_contact(phone: str, contact_data: ContactUpdate):
    """Update contact by phone number."""
    logger.info("="*50)
    logger.info(f"Updating contact: {phone}")
    return await contacts_controller.update_contact(phone, contact_data)

@router.delete("/contacts/{phone}")
async def delete_contact(phone: str):
    """Delete contact by phone number."""
    logger.info("="*50)
    logger.info(f"Deleting contact: {phone}")
    return await contacts_controller.delete_contact(phone) 