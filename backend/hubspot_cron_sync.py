#!/usr/bin/env python3
"""
HubSpot Contact Sync Cron Job
This script fetches contacts from HubSpot and stores them in the database.
Run this script to set up a cron job that executes every 2 minutes.
"""

import os
import sys
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from crontab import CronTab

# Add the current directory to Python path to import local modules
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from services.hubspot_service import HubspotService
from services.prisma_service import PrismaService

# Setup logging
log_file = current_dir / "cron_sync.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def sync_hubspot_contacts():
    """
    Fetch contacts from HubSpot and store them in the database
    """
    logger.info("Starting HubSpot contact sync...")
    
    prisma_service = None
    try:
        # Initialize services
        hubspot_service = HubspotService()
        prisma_service = PrismaService()
        
        # Connect to database
        await prisma_service.connect()
        logger.info("Connected to database")
        
        # Fetch contacts from HubSpot
        contacts = hubspot_service.get_contacts(limit=500)
        logger.info(f"Fetched {len(contacts)} contacts from HubSpot")
        
        # Filter contacts (excluding unqualified and open deal)
        filtered_contacts = [
            contact for contact in contacts
            if contact.get('properties', {}).get('hs_lead_status', '').lower() not in ['unqualified', 'open deal']
        ]
        logger.info(f"Filtered to {len(filtered_contacts)} qualified contacts")
        
        # Store/update contacts in database
        synced_count = 0
        for contact in filtered_contacts:
            try:
                contact_data = extract_contact_data(contact)
                
                # Check if contact exists (by email or HubSpot ID)
                existing_contact = None
                if contact_data['email']:
                    existing_contact = await prisma_service.get_contact_by_email(contact_data['email'])
                
                if not existing_contact and contact_data['hubspot_id']:
                    existing_contact = await prisma_service.get_contact_by_hubspot_id(contact_data['hubspot_id'])
                
                if existing_contact:
                    # Update existing contact
                    await prisma_service.update_contact(existing_contact.id, contact_data)
                    logger.debug(f"Updated contact: {contact_data['email']}")
                else:
                    # Create new contact
                    await prisma_service.create_contact(contact_data)
                    logger.debug(f"Created new contact: {contact_data['email']}")
                
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Error processing contact {contact.get('id', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Successfully synced {synced_count} contacts")
        
    except Exception as e:
        logger.error(f"Error during HubSpot sync: {str(e)}")
        raise
    finally:
        # Cleanup database connection
        if prisma_service:
            await prisma_service.disconnect()
            logger.info("Disconnected from database")

def extract_contact_data(hubspot_contact):
    """
    Extract relevant data from HubSpot contact for database storage
    """
    properties = hubspot_contact.get('properties', {})
    
    return {
        'hubspot_id': hubspot_contact.get('id'),
        'email': properties.get('email', ''),
        'first_name': properties.get('firstname', ''),
        'last_name': properties.get('lastname', ''),
        'phone': properties.get('phone', ''),
        'mobile_phone': properties.get('mobilephone', ''),
        'lifecycle_stage': properties.get('lifecyclestage', ''),
        'lead_status': properties.get('hs_lead_status', ''),
        'last_synced': datetime.now()
    }

def setup_cron_job():
    """
    Set up a cron job to run the sync every 2 minutes
    """
    logger.info("Setting up cron job...")
    
    # Get the current user's crontab
    cron = CronTab(user=True)
    
    # Remove any existing jobs for this script
    script_path = str(Path(__file__).absolute())
    python_path = sys.executable
    
    # Remove existing jobs
    existing_jobs = list(cron.find_comment('hubspot-contact-sync'))
    for job in existing_jobs:
        cron.remove(job)
        logger.info("Removed existing cron job")
    
    # Create new cron job to run every 2 minutes
    job = cron.new(command=f'{python_path} {script_path} --run-sync', comment='hubspot-contact-sync')
    job.setall('*/2 * * * *')  # Every 2 minutes
    
    # Write the cron job
    cron.write()
    logger.info("Cron job created successfully!")
    logger.info(f"Job will run every 2 minutes: */2 * * * *")
    logger.info(f"Command: {python_path} {script_path} --run-sync")
    
    # Display current cron jobs
    logger.info("\nCurrent cron jobs:")
    for job in cron:
        logger.info(f"  {job}")

def remove_cron_job():
    """
    Remove the cron job
    """
    logger.info("Removing cron job...")
    cron = CronTab(user=True)
    
    # Remove jobs with our comment
    existing_jobs = list(cron.find_comment('hubspot-contact-sync'))
    removed_count = 0
    for job in existing_jobs:
        cron.remove(job)
        removed_count += 1
    
    if removed_count > 0:
        cron.write()
        logger.info(f"Removed {removed_count} cron job(s)")
    else:
        logger.info("No cron jobs found to remove")

async def main():
    """
    Main function to handle command line arguments
    """
    if len(sys.argv) > 1:
        if sys.argv[1] == '--run-sync':
            # This is called by the cron job
            await sync_hubspot_contacts()
        elif sys.argv[1] == '--setup':
            # Set up the cron job
            setup_cron_job()
        elif sys.argv[1] == '--remove':
            # Remove the cron job
            remove_cron_job()
        elif sys.argv[1] == '--test':
            # Test the sync function once
            logger.info("Running test sync...")
            await sync_hubspot_contacts()
        else:
            print("Usage:")
            print("  python hubspot_cron_sync.py --setup    # Set up cron job")
            print("  python hubspot_cron_sync.py --remove   # Remove cron job")
            print("  python hubspot_cron_sync.py --test     # Test sync once")
            print("  python hubspot_cron_sync.py --run-sync # Run sync (called by cron)")
    else:
        print("Usage:")
        print("  python hubspot_cron_sync.py --setup    # Set up cron job")
        print("  python hubspot_cron_sync.py --remove   # Remove cron job")
        print("  python hubspot_cron_sync.py --test     # Test sync once")

if __name__ == "__main__":
    asyncio.run(main())