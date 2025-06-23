# celery_app.py
from celery import Celery
from config import REDIS_HOST_URI, REDIS_PASS
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'hubspot_call_queue',
    broker=f'redis://default:{REDIS_PASS}@{REDIS_HOST_URI}:11068/0',
    backend=f'redis://default:{REDIS_PASS}@{REDIS_HOST_URI}:11068/0',
    include=['tasks.call_tasks']  # Import task modules
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # Process one task at a time
    result_expires=3600,  # Results expire after 1 hour
    worker_redirect_stdouts=False,  # Prevent LoggingProxy error
    worker_redirect_stdouts_level='INFO',  # Still log at INFO level
    task_routes={
        'tasks.call_tasks.make_call': {'queue': 'call_queue'},
        'tasks.call_tasks.process_contact_calls': {'queue': 'contact_queue'},
    },
    # Task retry configuration
    task_default_retry_delay=60,  # Retry after 60 seconds
    task_max_retries=3,
    # Queue configuration
    task_default_queue='default',
    task_queues={
        'call_queue': {
            'routing_key': 'call_queue',
        },
        'contact_queue': {
            'routing_key': 'contact_queue',
        },
    }
)

if __name__ == '__main__':
    celery_app.start()