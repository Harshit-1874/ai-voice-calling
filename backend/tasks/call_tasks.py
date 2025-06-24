# tasks/call_tasks.py
from celery import Celery
from celery.exceptions import Retry
from celery_app import celery_app
import redis
from services.prisma_service import PrismaService
from controllers.call_controller import CallController
from services.redis_service import RedisService
import logging
import asyncio
import json
from config import REDIS_HOST_URI, REDIS_PASS
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def make_call(self, contact_data: Dict[str, Any], call_params: Dict[str, Any] = None):
    """
    Make a call to a specific contact
    
    Args:
        contact_data: Contact information from HubSpot
        call_params: Additional call parameters (priority, delay, etc.)
    """
    redis_client = redis.StrictRedis(
        host=REDIS_HOST_URI,
        port=11068,
        password=REDIS_PASS,
        decode_responses=True,
        username="default",
    )
    lock = redis_client.lock("active_call_lock", timeout=600)
    have_lock = lock.acquire(blocking=False)
    if not have_lock:
        logger.info("Another call is in progress. Retrying...")
        raise self.retry(exc=Exception("Call in progress"), countdown=30)
    try:
        logger.info(f"Starting call task for contact: {contact_data.get('email', 'unknown')}")
        
        # Extract phone number
        phone = contact_data.get('phone') or contact_data.get('mobile_phone')
        if not phone:
            logger.warning(f"No phone number found for contact: {contact_data.get('email', 'unknown')}")
            return {
                'success': False,
                'error': 'No phone number available',
                'contact_id': contact_data.get('hubspot_id')
            }
        
        # Create call controller and initiate call
        # Note: We need to handle async properly in Celery
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            call_controller = CallController()
            
            # Create a mock request object for the call
            from fastapi import Request
            from unittest.mock import Mock
            
            mock_request = Mock(spec=Request)
            mock_request.url.hostname = "your-domain.com"  # Replace with your actual domain
            
            result = loop.run_until_complete(
                call_controller.initiate_call(phone, mock_request)
            )
            
            # Update Redis with call status
            redis_service = RedisService()
            call_key = f"call:{result['call_sid']}"
            redis_service.client.setex(
                call_key, 
                3600,  # Expire after 1 hour
                json.dumps({
                    'contact_id': contact_data.get('hubspot_id'),
                    'call_sid': result['call_sid'],
                    'status': 'initiated',
                    'initiated_at': datetime.now().isoformat(),
                    'phone': phone,
                    'email': contact_data.get('email')
                })
            )
            
            logger.info(f"Call initiated successfully: {result['call_sid']}")
            return {
                'success': True,
                'call_sid': result['call_sid'],
                'contact_id': contact_data.get('hubspot_id'),
                'phone': phone
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error making call for contact {contact_data.get('email', 'unknown')}: {str(e)}")
        
        # Update Redis with error status
        try:
            redis_service = RedisService()
            error_key = f"call_error:{contact_data.get('hubspot_id', 'unknown')}"
            redis_service.client.setex(
                error_key,
                3600,
                json.dumps({
                    'contact_id': contact_data.get('hubspot_id'),
                    'error': str(e),
                    'failed_at': datetime.now().isoformat(),
                    'retry_count': self.request.retries
                })
            )
        except Exception as redis_error:
            logger.error(f"Error updating Redis with call error: {str(redis_error)}")
        
        raise self.retry(exc=e, countdown=60)

    finally:
        if have_lock:
            lock.release()
            logger.info("Released active call lock")
        else:
            logger.warning("Failed to acquire active call lock")
@celery_app.task(bind=True)
def process_contact_calls(self, contact_list: List[Dict[str, Any]], batch_size: int = 5, delay_between_calls: int = 30):
    """
    Process a list of contacts and queue calls for them
    
    Args:
        contact_list: List of contact data from HubSpot
        batch_size: Number of calls to process in parallel
        delay_between_calls: Delay in seconds between each call
    """
    try:
        logger.info(f"Processing {len(contact_list)} contacts for calls")
        
        redis_service = RedisService()
        
        # Store batch info in Redis
        batch_id = f"batch:{int(time.time())}"
        redis_service.client.setex(
            batch_id,
            7200,  # Expire after 2 hours
            json.dumps({
                'total_contacts': len(contact_list),
                'status': 'processing',
                'started_at': datetime.now().isoformat(),
                'batch_size': batch_size,
                'delay_between_calls': delay_between_calls
            })
        )
        
        successful_calls = 0
        failed_calls = 0
        
        # Process contacts in batches
        for i in range(0, len(contact_list), batch_size):
            batch = contact_list[i:i + batch_size]
            
            logger.info(f"Processing batch {i//batch_size + 1} with {len(batch)} contacts")
            
            # Queue calls for this batch
            for contact in batch:
                try:
                    # Add call priority based on lead status
                    priority = get_call_priority(contact)
                    
                    # Queue the call with delay
                    make_call.apply_async(
                        args=[contact],
                        kwargs={'call_params': {'priority': priority}},
                        countdown=delay_between_calls * (i + batch.index(contact)),
                        priority=priority
                    )
                    
                    successful_calls += 1
                    
                except Exception as e:
                    logger.error(f"Error queuing call for contact {contact.get('email', 'unknown')}: {str(e)}")
                    failed_calls += 1
            
            # Small delay between batches
            if i + batch_size < len(contact_list):
                time.sleep(2)
        
        # Update batch status in Redis
        redis_service.client.setex(
            batch_id,
            7200,
            json.dumps({
                'total_contacts': len(contact_list),
                'status': 'completed',
                'started_at': datetime.now().isoformat(),
                'completed_at': datetime.now().isoformat(),
                'successful_calls': successful_calls,
                'failed_calls': failed_calls,
                'batch_size': batch_size,
                'delay_between_calls': delay_between_calls
            })
        )
        
        logger.info(f"Batch processing completed. Success: {successful_calls}, Failed: {failed_calls}")
        
        return {
            'batch_id': batch_id,
            'total_contacts': len(contact_list),
            'successful_calls': successful_calls,
            'failed_calls': failed_calls
        }
        
    except Exception as e:
        logger.error(f"Error processing contact calls: {str(e)}")
        raise

@celery_app.task
def cleanup_old_call_data():
    """
    Cleanup old call data from Redis
    """
    try:
        redis_service = RedisService()
        
        # Get all call keys
        call_keys = redis_service.client.keys("call:*")
        error_keys = redis_service.client.keys("call_error:*")
        batch_keys = redis_service.client.keys("batch:*")
        
        cleaned_count = 0
        
        # Clean up old call data (older than 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for key in call_keys + error_keys + batch_keys:
            try:
                data = json.loads(redis_service.client.get(key) or '{}')
                
                # Check if data is old
                created_at = data.get('initiated_at') or data.get('failed_at') or data.get('started_at')
                if created_at:
                    created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00').replace('+00:00', ''))
                    if created_time < cutoff_time:
                        redis_service.client.delete(key)
                        cleaned_count += 1
                        
            except Exception as e:
                logger.error(f"Error cleaning up key {key}: {str(e)}")
                continue
        
        logger.info(f"Cleaned up {cleaned_count} old call records from Redis")
        return {'cleaned_count': cleaned_count}
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise

def get_call_priority(contact: Dict[str, Any]) -> int:
    """
    Determine call priority based on contact data
    Higher number = higher priority
    """
    lead_status = contact.get('hsLeadStatus', '').lower()
    
    # Priority mapping
    priority_map = {
        'qualified': 9,
        'lead': 8,
        'marketing qualified lead': 7,
        'sales qualified lead': 9,
        'new': 6,
        'customer': 5,
        'evangelist': 4,
        'other': 3
    }
    
    return priority_map.get(lead_status, 5)  # Default priority 5