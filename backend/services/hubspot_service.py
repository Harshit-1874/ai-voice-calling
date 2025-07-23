import os
import logging
from hubspot import HubSpot
from hubspot.crm.contacts import ApiException as ContactsApiException, SimplePublicObjectInput, Filter, FilterGroup, PublicObjectSearchRequest
from hubspot.crm.objects.notes import SimplePublicObjectInput as NoteInput
from config import HUBSPOT_ACCESS_TOKEN

logger = logging.getLogger(__name__)

class HubspotService:
    def __init__(self):
        if not HUBSPOT_ACCESS_TOKEN:
            raise ValueError("HubSpot API key not found in environment variables")
        self.client = HubSpot(access_token=HUBSPOT_ACCESS_TOKEN)
        logger.info("HubspotService initialized")

    def get_contacts(self, limit: int = 100):
        try:
            contacts = self.client.crm.contacts.get_all(
                limit=limit,
                properties=["phone", "mobilephone", "lifecyclestage", "hs_lead_status", 'email', 'firstname', 'lastname']
            )
            # logger.info(f"Fetched {len(contacts)} contacts from HubSpot")
            # Convert each contact to dict
            contacts_dicts = [contact.to_dict() for contact in contacts]
            return contacts_dicts
        except ContactsApiException as e:
            logger.error(f"HubSpot Contacts API error: {e}")
            raise

    def update_status(self, contact_id, status):
        try:
            input_data = SimplePublicObjectInput(
                properties={"hs_lead_status": status}
            )
            self.client.crm.contacts.basic_api.update(
                contact_id,
                simple_public_object_input=input_data
            )
            logger.info(f"Updated contact {contact_id} status to {status}")
        except ContactsApiException as e:
            logger.error(f"Error updating contact {contact_id}: {e}")
            raise

    def create_note_for_contact(self, phone_number, transcription, note_content):
        try:
            filters = Filter(property_name="phone", operator="EQ", value=phone_number)
            filter_group = FilterGroup(filters=[filters])
            search_req = PublicObjectSearchRequest(filter_groups=[filter_group])

            search_res = self.client.crm.contacts.search_api.do_search(
                public_object_search_request=search_req
            )
            if not search_res.results:
                logger.warning(f"No contact found with phone {phone_number}")
                return

            contact_id = search_res.results[0].id

            input_data = SimplePublicObjectInput(
                properties={"last_call_note": note_content, "call_transcription": transcription}
            )

            self.client.crm.contacts.basic_api.update(
                contact_id,
                simple_public_object_input=input_data
            )
            logger.info(f"Created note for contact {contact_id}")
        except Exception as e:
            logger.error(f"Error creating note for contact {contact_id}: {e}")
            raise

