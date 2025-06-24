# celery_app.py
from celery import Celery
from config import REDIS_HOST_URI, REDIS_PASS
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_celery_app() -> Celery:
    """
    Create and configure Celery app
    """
    celery_app = Celery(
        'hubspot_call_queue',
        broker=f'redis://default:{REDIS_PASS}@{REDIS_HOST_URI}:11068/0',
        backend=f'redis://default:{REDIS_PASS}@{REDIS_HOST_URI}:11068/0'
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
        worker_prefetch_multiplier=1,
        result_expires=3600,
        worker_redirect_stdouts=False,
        worker_redirect_stdouts_level='INFO',
        task_routes={
            'tasks.call_tasks.make_call': {'queue': 'call_queue'},
            'tasks.call_tasks.process_contact_calls': {'queue': 'contact_queue'},
            'tasks.call_tasks.cleanup_old_call_data': {'queue': 'default'},
        },
        task_default_retry_delay=60,
        task_max_retries=3,
        task_default_queue='default',
        task_queues={
            'call_queue': {'routing_key': 'call_queue'},
            'contact_queue': {'routing_key': 'contact_queue'},
        },
        # Important: Don't set worker-specific configs here when embedding
        imports=['tasks.call_tasks']
    )

    return celery_app

# Create the Celery app instance
celery_app = create_celery_app()