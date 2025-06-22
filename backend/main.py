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

# Background task references
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
            from services.prisma_service import PrismaService
            
            # Initialize services
            hubspot_service = HubspotService()
            prisma_service = getattr(app.state, "prisma_service", None)
            if not prisma_service:
                return {
                    "status": "error",
                    "error": "Database connection not available"
                }
            
            try:
                # Connect to database
                await prisma_service.connect()
                logger.info("Connected to database for sync")
                
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
            finally:
                # Cleanup database connection
                try:
                    await prisma_service.disconnect()
                    logger.debug("Disconnected from database after sync")
                except Exception as e:
                    logger.error(f"Error disconnecting from database: {str(e)}")
                    
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
    
    # Start HubSpot sync background task
    try:
        sync_task = asyncio.create_task(hubspot_sync_worker())
        logger.info("Started HubSpot sync background task")
        app.state.sync_method = "background_task"
        app.state.sync_task = sync_task
    except Exception as e:
        logger.error(f"Failed to start background sync task: {str(e)}")
        app.state.sync_method = "none"
    
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

# Add a health check endpoint to verify sync status
@app.get("/health/sync")
async def check_sync_status():
    """
    Check the status of HubSpot sync
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

# Add Celery worker health check
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

# Add queue status endpoint
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

# Add manual sync trigger endpoint
@app.post("/sync/trigger")
async def trigger_manual_sync():
    """
    Manually trigger a HubSpot contact sync
    """
    try:
        logger.info("Manual sync triggered via API")
        
        from services.hubspot_service import HubspotService
        from services.prisma_service import PrismaService
        
        # Initialize services
        hubspot_service = HubspotService()
        prisma_service = getattr(app.state, "prisma_service", None)
        if not prisma_service:
            return {
                "status": "error",
                "error": "Database connection not available"
            }
        
        try:
            # Connect to database
            # await prisma_service.connect()
            
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
            
        # finally:
            # await prisma_service.disconnect()
            
    except Exception as e:
        logger.error(f"Error in manual sync: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

# Add endpoint to queue calls
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

# Add endpoint to queue batch calls
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
        logger.info("Starting uvicorn server with integrated Celery worker")
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