import logging
import sys
import platform
import asyncio
import threading
import time
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from hubspot_cron_sync import extract_hubspot_temp_data, extract_contact_data
from contextlib import asynccontextmanager
import uvicorn
from routes.call_routes import router as call_router
from routes.hubspot_routes import router as hubspot_router
from routes.contact_routes import router as contact_router
from config import validate_env, HOST, PORT, DEBUG

# Import Celery components
from celery_app import celery_app
from services.queue_service import QueueService

current_dir = Path(__file__).parent
log_file = current_dir / "app.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info("="*50)
logger.info("Application Starting")
logger.info(f"Start Time: {datetime.now()}")
logger.info(f"Log file location: {log_file}")
logger.info("="*50)

# Global task references
sync_task = None
celery_worker_thread = None

def start_celery_worker():
    """
    Start Celery worker in a separate thread
    """
    try:
        logger.info("Starting Celery worker...")
        
        # Configure Celery worker
        worker = celery_app.Worker(
            loglevel='INFO',
            queues=['default', 'call_queue', 'contact_queue'],
            concurrency=2,  # Number of worker processes
            prefetch_multiplier=1,
            max_tasks_per_child=1000,
        )
        
        # Start the worker
        worker.start()
        
    except Exception as e:
        logger.error(f"Error starting Celery worker: {str(e)}")
        raise

def celery_worker_thread_func():
    """
    Function to run Celery worker in a separate thread
    """
    try:
        logger.info("Starting Celery worker thread...")
        start_celery_worker()
    except Exception as e:
        logger.error(f"Celery worker thread error: {str(e)}")

def setup_unix_cron_job():
    """
    Set up cron job for Unix/Linux systems
    """
    try:
        from crontab import CronTab
        
        # Try different approaches to get crontab
        cron = None
        
        try:
            import getpass
            current_user = getpass.getuser()
            logger.info(f"Attempting to set up cron job for user: {current_user}")
            cron = CronTab(user=current_user)
        except Exception as e1:
            logger.warning(f"Failed to get crontab by username: {e1}")
            
            try:
                cron = CronTab(user=True)
            except Exception as e2:
                logger.warning(f"Failed to get crontab with user=True: {e2}")
                raise Exception("Could not access crontab")
        
        # Define the cron job command
        script_path = current_dir / "hubspot_cron_sync.py"
        python_path = sys.executable
        cron_command = f'{python_path} {script_path} --run-sync'
        
        # Check if the cron job already exists
        existing_jobs = list(cron.find_comment('hubspot-contact-sync'))
        
        if existing_jobs:
            logger.info("HubSpot cron job already exists")
            return "cron_job"
        
        # Create new cron job to run every 2 minutes
        job = cron.new(command=cron_command, comment='hubspot-contact-sync')
        job.setall('*/2 * * * *')  # Every 2 minutes
        
        # Check if the cron job is valid
        if job.is_valid():
            cron.write()
            logger.info("HubSpot cron job created successfully!")
            logger.info(f"Job schedule: */2 * * * * (every 2 minutes)")
            logger.info(f"Command: {cron_command}")
            return "cron_job"
        else:
            logger.error("Failed to create valid cron job")
            raise Exception("Invalid cron job")
            
    except Exception as e:
        logger.error(f"Error setting up Unix cron job: {str(e)}")
        raise

def setup_hubspot_sync():
    """
    Set up HubSpot sync based on the operating system
    """
    os_name = platform.system()
    logger.info(f"Operating System: {os_name}")
    
    if os_name == "Windows":
        logger.info("Windows detected - using in-app background task for HubSpot sync")
        return "background_task"
    else:
        # Try to set up cron job for Unix/Linux systems
        try:
            from crontab import CronTab
            logger.info("Unix/Linux detected - attempting to set up cron job")
            return setup_unix_cron_job()
        except ImportError:
            logger.warning("crontab library not available, falling back to background task")
            return "background_task"
        except Exception as e:
            logger.error(f"Error setting up cron job: {str(e)}")
            logger.info("Falling back to background task")
            return "background_task"

async def hubspot_sync_worker():
    """
    Background worker that runs HubSpot sync every 2 minutes
    """
    logger.info("Starting HubSpot sync background worker...")
    
    while True:
        try:
            await asyncio.sleep(120)  # Wait 2 minutes (120 seconds)
            
            logger.info("Running HubSpot contact sync...")
            
            # Import here to avoid circular imports
            from services.hubspot_service import HubspotService
            
            # Initialize services
            hubspot_service = HubspotService()
            prisma_service = getattr(app.state, "prisma_service", None)
            if not prisma_service:
                logger.error("Database connection not available for sync")
                continue
            
            try:
                # Fetch contacts from HubSpot
                contacts = hubspot_service.get_contacts(limit=500)
                logger.info(f"Fetched {len(contacts)} contacts from HubSpot")
                
                # Filter contacts (excluding unqualified and open deal)
                filtered_contacts = [
                    contact for contact in contacts
                    if contact.get('properties', {}).get('hs_lead_status', '').lower() not in ['unqualified', 'open deal']
                ]
                logger.info(f"Filtered to {len(filtered_contacts)} qualified contacts")

                synced_temp_count = 0
                for contact in filtered_contacts:
                    try:
                        temp_data = extract_hubspot_temp_data(contact)
                        await prisma_service.upsert_hubspot_temp_data(temp_data)
                        synced_temp_count += 1
                    except Exception as e:
                        logger.error(f"Error syncing HubspotTempData for contact {contact.get('id', 'unknown')}: {str(e)}")
                        continue
                
                logger.info(f"Successfully synced {synced_temp_count} contacts")
                
            except Exception as e:
                logger.error(f"Error during HubSpot sync: {str(e)}")
                    
        except asyncio.CancelledError:
            logger.info("HubSpot sync worker cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in sync worker: {str(e)}")
            # Continue the loop even if there's an error

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sync_task, celery_worker_thread
    
    logger.info("Starting application lifespan")
    validate_env()
    logger.info("All environment variables validated")
    
    # Initialize database connection
    try:
        from services.prisma_service import PrismaService
        prisma_service = PrismaService()
        await prisma_service.connect()
        logger.info("Database connection established")
        
        # Store the service in app state for access in routes
        app.state.prisma_service = prisma_service
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        logger.error("Application will start without database functionality")
        app.state.prisma_service = None
    
    # Initialize Queue Service
    try:
        queue_service = QueueService()
        app.state.queue_service = queue_service
        logger.info("Queue service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize queue service: {str(e)}")
        app.state.queue_service = None
    
    # Start Celery worker in a separate thread
    try:
        celery_worker_thread = threading.Thread(
            target=celery_worker_thread_func,
            daemon=True  # Dies when main thread dies
        )
        celery_worker_thread.start()
        logger.info("Celery worker thread started")
        
        # Give the worker a moment to start
        await asyncio.sleep(2)
        
        app.state.celery_worker_status = "running"
    except Exception as e:
        logger.error(f"Failed to start Celery worker: {str(e)}")
        app.state.celery_worker_status = "failed"
    
    # Set up HubSpot sync based on OS
    sync_method = setup_hubspot_sync()
    
    # Start background sync task if using background task method
    if sync_method == "background_task":
        try:
            sync_task = asyncio.create_task(hubspot_sync_worker())
            logger.info("Started HubSpot sync background task")
            app.state.sync_method = "background_task"
            app.state.sync_task = sync_task
        except Exception as e:
            logger.error(f"Failed to start background sync task: {str(e)}")
            app.state.sync_method = "none"
    else:
        app.state.sync_method = sync_method
        app.state.sync_task = None
    
    yield
    
    # Cleanup
    logger.info("Starting application cleanup...")
    
    # Stop HubSpot sync task
    if sync_task and not sync_task.done():
        logger.info("Stopping HubSpot sync background task...")
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            logger.info("Background sync task stopped")
        except Exception as e:
            logger.error(f"Error stopping background task: {str(e)}")
    
    # Stop Celery worker
    if celery_worker_thread and celery_worker_thread.is_alive():
        logger.info("Stopping Celery worker...")
        try:
            # Gracefully shutdown Celery
            celery_app.control.shutdown()
            # Give it a moment to shut down
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error stopping Celery worker: {str(e)}")
    
    # Close database connection
    if hasattr(app.state, 'prisma_service') and app.state.prisma_service:
        try:
            await app.state.prisma_service.disconnect()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {str(e)}")
    
    logger.info("Application cleanup completed")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(call_router)
app.include_router(hubspot_router)
app.include_router(contact_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Unified sync status check endpoint
@app.get("/health/sync")
async def check_sync_status():
    """
    Check the status of HubSpot sync (both background task and cron job)
    """
    try:
        sync_method = getattr(app.state, 'sync_method', 'none')
        sync_task_obj = getattr(app.state, 'sync_task', None)
        
        if sync_method == "background_task":
            if sync_task_obj and not sync_task_obj.done():
                return {
                    "status": "active",
                    "method": "background_task",
                    "message": "Background sync task is running (every 2 minutes)",
                    "task_status": "running"
                }
            else:
                return {
                    "status": "inactive",
                    "method": "background_task",
                    "message": "Background sync task is not running",
                    "task_status": "stopped"
                }
        elif sync_method == "cron_job":
            # For Unix systems with cron
            try:
                from crontab import CronTab
                cron = CronTab(user=True)
                existing_jobs = list(cron.find_comment('hubspot-contact-sync'))
                
                if existing_jobs:
                    job_details = []
                    for job in existing_jobs:
                        job_details.append({
                            "schedule": str(job),
                            "command": str(job.command),
                            "enabled": job.is_enabled(),
                            "valid": job.is_valid()
                        })
                    
                    return {
                        "status": "active",
                        "method": "cron_job",
                        "jobs_count": len(existing_jobs),
                        "jobs": job_details
                    }
                else:
                    return {
                        "status": "inactive",
                        "method": "cron_job",
                        "message": "No cron jobs found"
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "method": "cron_job",
                    "error": str(e)
                }
        else:
            return {
                "status": "inactive",
                "method": "none",
                "message": "No sync method configured"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# Celery worker health check
@app.get("/health/celery")
async def check_celery_status():
    """
    Check the status of Celery worker
    """
    try:
        celery_status = getattr(app.state, 'celery_worker_status', 'unknown')
        
        # Try to ping Celery
        try:
            # This will raise an exception if no workers are available
            result = celery_app.control.ping(timeout=1)
            active_workers = len(result) if result else 0
            
            return {
                "status": "active" if active_workers > 0 else "inactive",
                "worker_status": celery_status,
                "active_workers": active_workers,
                "workers": result
            }
        except Exception as ping_error:
            return {
                "status": "inactive",
                "worker_status": celery_status,
                "error": str(ping_error),
                "active_workers": 0
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# Queue status endpoint
@app.get("/health/queue")
async def check_queue_status():
    """
    Check the status of the task queue
    """
    try:
        queue_service = getattr(app.state, 'queue_service', None)
        if not queue_service:
            return {
                "status": "error",
                "message": "Queue service not initialized"
            }
        
        stats = queue_service.get_queue_stats()
        return {
            "status": "active",
            "stats": stats
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# Manual sync trigger endpoint
@app.post("/sync/trigger")
async def trigger_manual_sync():
    """
    Manually trigger a HubSpot contact sync
    """
    try:
        logger.info("Manual sync triggered via API")
        
        from services.hubspot_service import HubspotService
        
        # Initialize services
        hubspot_service = HubspotService()
        prisma_service = getattr(app.state, "prisma_service", None)
        if not prisma_service:
            return {
                "status": "error",
                "error": "Database connection not available"
            }
        
        try:
            # Fetch contacts from HubSpot
            contacts = hubspot_service.get_contacts(limit=500)
            
            # Filter contacts
            filtered_contacts = [
                contact for contact in contacts
                if contact.get('properties', {}).get('hs_lead_status', '').lower() not in ['unqualified', 'open deal']
            ]
            
            # Store/update contacts in database
            synced_temp_count = 0
            errors = []

            for contact in filtered_contacts:
                try:
                    temp_data = extract_hubspot_temp_data(contact)
                    await prisma_service.upsert_hubspot_temp_data(temp_data)
                    synced_temp_count += 1
                except Exception as e:
                    logger.error(f"Error syncing HubspotTempData for contact {contact.get('id', 'unknown')}: {str(e)}")
                    errors.append(f"Error syncing HubspotTempData for contact {contact.get('id', 'unknown')}: {str(e)}")
                    continue
            
            return {
                "status": "success",
                "message": f"Manual sync completed",
                "total_fetched": len(contacts),
                "total_filtered": len(filtered_contacts),
                "synced_count": synced_temp_count,
                "errors_count": len(errors),
                "errors": errors[:10]  # Return first 10 errors
            }
        except Exception as e:
            logger.error(f"Error during manual sync: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
            
    except Exception as e:
        logger.error(f"Error in manual sync: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

# Queue management endpoints
@app.post("/queue/call")
async def queue_single_call(contact_data: dict, delay: int = 0, priority: int = 5):
    """
    Queue a single call
    """
    try:
        queue_service = getattr(app.state, 'queue_service', None)
        if not queue_service:
            return {
                "status": "error",
                "message": "Queue service not available"
            }
        
        task_id = queue_service.queue_single_call(contact_data, delay, priority)
        return {
            "status": "success",
            "task_id": task_id,
            "message": f"Call queued for {contact_data.get('email', 'unknown')}"
        }
        
    except Exception as e:
        logger.error(f"Error queuing call: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@app.post("/queue/batch")
async def queue_batch_calls(contacts: list, batch_size: int = 5, delay_between_calls: int = 30):
    """
    Queue batch calls
    """
    try:
        queue_service = getattr(app.state, 'queue_service', None)
        if not queue_service:
            return {
                "status": "error",
                "message": "Queue service not available"
            }
        
        task_id = queue_service.queue_batch_calls(contacts, batch_size, delay_between_calls)
        return {
            "status": "success",
            "task_id": task_id,
            "message": f"Batch of {len(contacts)} calls queued"
        }
        
    except Exception as e:
        logger.error(f"Error queuing batch calls: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    try:
        logger.info("Starting uvicorn server with integrated Celery worker and OS-based sync")
        uvicorn.run(
            app, 
            host=HOST, 
            port=PORT,
            log_level="debug",
            reload=False,
            workers=1,
            loop="asyncio"
        )
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        raise