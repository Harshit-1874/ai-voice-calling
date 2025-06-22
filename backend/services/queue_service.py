# services/queue_service.py
from services.redis_service import RedisService
from tasks.call_tasks import make_call, process_contact_calls, cleanup_old_call_data
from celery_app import celery_app
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class QueueService:
    def __init__(self):
        self.redis_service = RedisService()
        
    def queue_single_call(self, contact_data: Dict[str, Any], delay: int = 0, priority: int = 5) -> str:
        """
        Queue a single call for a contact
        
        Args:
            contact_data: Contact information
            delay: Delay in seconds before making the call
            priority: Call priority (1-10, higher = more important)
            
        Returns:
            Task ID
        """
        try:
            task = make_call.apply_async(
                args=[contact_data],
                kwargs={'call_params': {'priority': priority}},
                countdown=delay,
                priority=priority
            )
            
            # Store task info in Redis
            task_key = f"task:{task.id}"
            self.redis_service.client.setex(
                task_key,
                3600,  # Expire after 1 hour
                json.dumps({
                    'task_id': task.id,
                    'contact_id': contact_data.get('hubspotId'),
                    'email': contact_data.get('email'),
                    'phone': contact_data.get('phone'),
                    'status': 'queued',
                    'priority': priority,
                    'queued_at': datetime.now().isoformat(),
                    'delay': delay
                })
            )
            
            logger.info(f"Queued call for contact {contact_data.get('email')} with task ID: {task.id}")
            return task.id
            
        except Exception as e:
            logger.error(f"Error queuing single call: {str(e)}")
            raise
    
    def queue_batch_calls(self, contacts: List[Dict[str, Any]], batch_size: int = 5, delay_between_calls: int = 30) -> str:
        """
        Queue batch calls for multiple contacts
        
        Args:
            contacts: List of contact data
            batch_size: Number of calls to process in parallel
            delay_between_calls: Delay between each call in seconds
            
        Returns:
            Batch task ID
        """
        try:
            task = process_contact_calls.apply_async(
                args=[contacts, batch_size, delay_between_calls]
            )
            
            # Store batch task info in Redis
            batch_key = f"batch_task:{task.id}"
            self.redis_service.client.setex(
                batch_key,
                7200,  # Expire after 2 hours
                json.dumps({
                    'task_id': task.id,
                    'total_contacts': len(contacts),
                    'batch_size': batch_size,
                    'delay_between_calls': delay_between_calls,
                    'status': 'queued',
                    'queued_at': datetime.now().isoformat()
                })
            )
            
            logger.info(f"Queued batch calls for {len(contacts)} contacts with task ID: {task.id}")
            return task.id
            
        except Exception as e:
            logger.error(f"Error queuing batch calls: {str(e)}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a queued task
        """
        try:
            # Get task from Celery
            task_result = celery_app.AsyncResult(task_id)
            
            # Get additional info from Redis
            task_key = f"task:{task_id}"
            batch_key = f"batch_task:{task_id}"
            
            redis_data = self.redis_service.client.get(task_key) or self.redis_service.client.get(batch_key)
            additional_info = json.loads(redis_data) if redis_data else {}
            
            return {
                'task_id': task_id,
                'status': task_result.status,
                'result': task_result.result if task_result.ready() else None,
                'info': task_result.info,
                **additional_info
            }
            
        except Exception as e:
            logger.error(f"Error getting task status: {str(e)}")
            return {
                'task_id': task_id,
                'status': 'UNKNOWN',
                'error': str(e)
            }
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics
        """
        try:
            # Get active tasks
            active_tasks = celery_app.control.inspect().active()
            
            # Get queue lengths
            queue_lengths = {}
            try:
                # This requires celery management commands
                queue_lengths = celery_app.control.inspect().active_queues()
            except Exception:
                pass
            
            # Get Redis stats
            call_keys = len(self.redis_service.client.keys("call:*"))
            task_keys = len(self.redis_service.client.keys("task:*"))
            batch_keys = len(self.redis_service.client.keys("batch:*"))
            error_keys = len(self.redis_service.client.keys("call_error:*"))
            
            return {
                'active_tasks': active_tasks,
                'queue_lengths': queue_lengths,
                'redis_stats': {
                    'active_calls': call_keys,
                    'queued_tasks': task_keys,
                    'batch_tasks': batch_keys,
                    'error_records': error_keys
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {str(e)}")
            return {'error': str(e)}
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a queued task
        """
        try:
            celery_app.control.revoke(task_id, terminate=True)
            
            # Update Redis status
            task_key = f"task:{task_id}"
            batch_key = f"batch_task:{task_id}"
            
            for key in [task_key, batch_key]:
                data = self.redis_service.client.get(key)
                if data:
                    task_data = json.loads(data)
                    task_data['status'] = 'cancelled'
                    task_data['cancelled_at'] = datetime.now().isoformat()
                    self.redis_service.client.setex(key, 3600, json.dumps(task_data))
                    break
            
            logger.info(f"Cancelled task: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {str(e)}")
            return False
    
    def schedule_cleanup(self) -> str:
        """
        Schedule cleanup of old call data
        """
        try:
            task = cleanup_old_call_data.apply_async()
            logger.info(f"Scheduled cleanup task: {task.id}")
            return task.id
            
        except Exception as e:
            logger.error(f"Error scheduling cleanup: {str(e)}")
            raise
    
    def get_recent_calls(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent call data from Redis
        """
        try:
            call_keys = self.redis_service.client.keys("call:*")
            calls = []
            
            for key in call_keys[-limit:]:  # Get last N calls
                try:
                    data = self.redis_service.client.get(key)
                    if data:
                        call_data = json.loads(data)
                        call_data['redis_key'] = key
                        calls.append(call_data)
                except Exception as e:
                    logger.error(f"Error parsing call data for key {key}: {str(e)}")
                    continue
            
            # Sort by initiated_at timestamp
            calls.sort(key=lambda x: x.get('initiated_at', ''), reverse=True)
            return calls
            
        except Exception as e:
            logger.error(f"Error getting recent calls: {str(e)}")
            return []
    
    def get_call_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent call errors from Redis
        """
        try:
            error_keys = self.redis_service.client.keys("call_error:*")
            errors = []
            
            for key in error_keys[-limit:]:  # Get last N errors
                try:
                    data = self.redis_service.client.get(key)
                    if data:
                        error_data = json.loads(data)
                        error_data['redis_key'] = key
                        errors.append(error_data)
                except Exception as e:
                    logger.error(f"Error parsing error data for key {key}: {str(e)}")
                    continue
            
            # Sort by failed_at timestamp
            errors.sort(key=lambda x: x.get('failed_at', ''), reverse=True)
            return errors
            
        except Exception as e:
            logger.error(f"Error getting call errors: {str(e)}")
            return []