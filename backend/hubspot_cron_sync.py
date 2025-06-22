#!/usr/bin/env python3
"""
HubSpot Contact Sync Cron Job with Call Queue Integration
This script fetches contacts from HubSpot, stores them in the database, and queues calls.
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
from services.queue_service import QueueService

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
    Fetch contacts from HubSpot, store them in the database, and queue calls
    """
    logger.info("Starting HubSpot contact sync...")
    
    prisma_service = None
    queue_service = None
    
    try:
        # Initialize services
        hubspot_service = HubspotService()
        prisma_service = PrismaService()
        queue_service = QueueService()
        
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
        
        # Sync to HubspotTempData table
        synced_temp_count = 0
        contacts_for_calling = []
        
        for contact in filtered_contacts:
            try:
                temp_data = extract_hubspot_temp_data(contact)
                await prisma_service.upsert_hubspot_temp_data(temp_data)
                synced_temp_count += 1
                
                # Prepare contact data for calling queue
                if should_queue_for_calling(contact):
                    contacts_for_calling.append(temp_data)
                    
            except Exception as e:
                logger.error(f"Error syncing HubspotTempData for contact {contact.get('id', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Successfully synced {synced_temp_count} contacts to HubspotTempData")
        
        # Queue calls for eligible contacts
        if contacts_for_calling:
            logger.info(f"Queuing calls for {len(contacts_for_calling)} contacts")
            
            try:
                # Separate contacts by priority
                high_priority_contacts = [
                    c for c in contacts_for_calling 
                    if c.get('hsLeadStatus', '').lower() in ['qualified', 'sales qualified lead']
                ]
                
                medium_priority_contacts = [
                    c for c in contacts_for_calling 
                    if c.get('hsLeadStatus', '').lower() in ['lead', 'marketing qualified lead']
                ]
                
                low_priority_contacts = [
                    c for c in contacts_for_calling 
                    if c not in high_priority_contacts and c not in medium_priority_contacts
                ]
                
                # Queue high priority contacts first (with minimal delay)
                if high_priority_contacts:
                    batch_id = queue_service.queue_batch_calls(
                        contacts=high_priority_contacts,
                        batch_size=3,  # Smaller batches for high priority
                        delay_between_calls=10  # Shorter delay
                    )
                    logger.info(f"Queued {len(high_priority_contacts)} high priority contacts (batch: {batch_id})")
                
                # Queue medium priority contacts
                if medium_priority_contacts:
                    batch_id = queue_service.queue_batch_calls(
                        contacts=medium_priority_contacts,
                        batch_size=5,
                        delay_between_calls=30
                    )
                    logger.info(f"Queued {len(medium_priority_contacts)} medium priority contacts (batch: {batch_id})")
                
                # Queue low priority contacts with longer delays
                if low_priority_contacts:
                    batch_id = queue_service.queue_batch_calls(
                        contacts=low_priority_contacts,
                        batch_size=8,
                        delay_between_calls=60  # Longer delay for low priority
                    )
                    logger.info(f"Queued {len(low_priority_contacts)} low priority contacts (batch: {batch_id})")
                
                # Schedule cleanup task
                cleanup_task_id = queue_service.schedule_cleanup()
                logger.info(f"Scheduled cleanup task: {cleanup_task_id}")
                
            except Exception as queue_error:
                logger.error(f"Error queuing calls: {str(queue_error)}")
                # Continue execution even if queuing fails
        else:
            logger.info("No contacts eligible for calling")
        
        # Get queue statistics
        try:
            stats = queue_service.get_queue_stats()
            logger.info(f"Queue stats: {stats.get('redis_stats', {})}")
        except Exception as stats_error:
            logger.warning(f"Could not get queue stats: {str(stats_error)}")
        
    except Exception as e:
        logger.error(f"Error during HubSpot sync: {str(e)}")
        raise
    finally:
        # Cleanup database connection
        if prisma_service:
            await prisma_service.disconnect()
            logger.info("Disconnected from database")

def should_queue_for_calling(hubspot_contact) -> bool:
    """
    Determine if a contact should be queued for calling
    """
    properties = hubspot_contact.get('properties', {})
    
    # Check if contact has a phone number
    phone = properties.get('phone') or properties.get('mobilephone')
    if not phone:
        return False
    
    # Check lead status
    lead_status = properties.get('hs_lead_status', '').lower()
    if lead_status in ['unqualified', 'open deal', 'customer', 'evangelist']:
        return False
    
    # Check if we've called recently (you might want to add this logic)
    # For now, we'll queue all qualified contacts
    
    # Check lifecycle stage
    lifecycle_stage = properties.get('lifecyclestage', '').lower()
    if lifecycle_stage in ['customer', 'evangelist']:
        return False
    
    return True

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
        # 'lifecycle_stage': properties.get('lifecyclestage', ''),
        'lead_status': properties.get('hs_lead_status', ''),
        'last_synced': datetime.now()
    }

def extract_hubspot_temp_data(hubspot_contact):
    """
    Extract relevant data for HubspotTempData table
    """
    properties = hubspot_contact.get('properties', {})
    return {
        'hubspotId': str(hubspot_contact.get('id', '')),
        'hsLeadStatus': properties.get('hs_lead_status', ''),
        'email': properties.get('email', ''),
        'phone': properties.get('phone', '') or properties.get('mobilephone', ''),
        'firstName': properties.get('firstname', ''),
        'lastName': properties.get('lastname', ''),
        'hubspotCreatedAt': properties.get('createdate', ''),
        # 'lifecycleStage': properties.get('lifecyclestage', '')
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
        elif sys.argv[1] == '--queue-stats':
            # Show queue statistics
            try:
                queue_service = QueueService()
                stats = queue_service.get_queue_stats()
                recent_calls = queue_service.get_recent_calls(20)
                errors = queue_service.get_call_errors(10)
                
                print("\n=== Queue Statistics ===")
                print(f"Active calls: {stats.get('redis_stats', {}).get('active_calls', 0)}")
                print(f"Queued tasks: {stats.get('redis_stats', {}).get('queued_tasks', 0)}")
                print(f"Batch tasks: {stats.get('redis_stats', {}).get('batch_tasks', 0)}")
                print(f"Error records: {stats.get('redis_stats', {}).get('error_records', 0)}")
                
                print(f"\n=== Recent Calls ({len(recent_calls)}) ===")
                for call in recent_calls[:5]:  # Show last 5
                    print(f"Contact: {call.get('email', 'N/A')} | Status: {call.get('status')} | Time: {call.get('initiated_at', 'N/A')}")
                
                print(f"\n=== Recent Errors ({len(errors)}) ===")
                for error in errors[:3]:  # Show last 3
                    print(f"Contact: {error.get('contact_id', 'N/A')} | Error: {error.get('error', 'N/A')[:50]}...")
                    
            except Exception as e:
                logger.error(f"Error getting queue statistics: {str(e)}")
        else:
            print("Usage:")
            print("  python hubspot_cron_sync.py --setup       # Set up cron job")
            print("  python hubspot_cron_sync.py --remove      # Remove cron job")
            print("  python hubspot_cron_sync.py --test        # Test sync once")
            print("  python hubspot_cron_sync.py --run-sync    # Run sync (called by cron)")
            print("  python hubspot_cron_sync.py --queue-stats # Show queue statistics")
    else:
        print("Usage:")
        print("  python hubspot_cron_sync.py --setup       # Set up cron job")
        print("  python hubspot_cron_sync.py --remove      # Remove cron job")
        print("  python hubspot_cron_sync.py --test        # Test sync once")
        print("  python hubspot_cron_sync.py --queue-stats # Show queue statistics")

if __name__ == "__main__":
    asyncio.run(main())