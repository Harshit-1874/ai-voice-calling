import logging
import sys
import platform
import asyncio
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

# Background task for HubSpot sync
sync_task = None

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
            prisma_service = PrismaService()
            
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
                
                
                # Store/update contacts in database
                # synced_count = 0
                # for contact in filtered_contacts:
                #     try:
                #         contact_data = extract_contact_data(contact)
                        
                #         # Check if contact exists (by email or HubSpot ID)
                #         existing_contact = None
                #         if contact_data['email']:
                #             existing_contact = await prisma_service.get_contact_by_email(contact_data['email'])
                        
                #         if not existing_contact and contact_data['hubspot_id']:
                #             existing_contact = await prisma_service.get_contact_by_hubspot_id(contact_data['hubspot_id'])
                        
                #         if existing_contact:
                #             # Update existing contact
                #             await prisma_service.update_contact(existing_contact.id, contact_data)
                #             logger.debug(f"Updated contact: {contact_data['email']}")
                #         else:
                #             # Create new contact
                #             await prisma_service.create_contact(contact_data)
                #             logger.debug(f"Created new contact: {contact_data['email']}")
                        
                #         synced_count += 1
                        
                #     except Exception as e:
                #         logger.error(f"Error processing contact {contact.get('id', 'unknown')}: {str(e)}")
                #         continue
                
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sync_task
    
    logger.info("Starting application lifespan")
    validate_env()
    logger.info("All environment variables validated")
    
    # Set up HubSpot sync
    sync_method = setup_hubspot_sync()
    
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
    if sync_task and not sync_task.done():
        logger.info("Stopping HubSpot sync background task...")
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            logger.info("Background sync task stopped")
        except Exception as e:
            logger.error(f"Error stopping background task: {str(e)}")
    
    if hasattr(app.state, 'prisma_service') and app.state.prisma_service:
        try:
            await app.state.prisma_service.disconnect()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {str(e)}")
    
    logger.info("Shutting down server...")

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
        prisma_service = PrismaService()
        
        try:
            # Connect to database
            await prisma_service.connect()
            
            # Fetch contacts from HubSpot
            contacts = hubspot_service.get_contacts(limit=500)
            
            # Filter contacts
            filtered_contacts = [
                contact for contact in contacts
                if contact.get('properties', {}).get('hs_lead_status', '').lower() not in ['unqualified', 'open deal']
            ]
            
            # Store/update contacts in database
            synced_count = 0
            errors = []

            synced_temp_count = 0
            for contact in filtered_contacts:
                try:
                    temp_data = extract_hubspot_temp_data(contact)
                    await prisma_service.upsert_hubspot_temp_data(temp_data)
                    synced_temp_count += 1
                except Exception as e:
                    logger.error(f"Error syncing HubspotTempData for contact {contact.get('id', 'unknown')}: {str(e)}")
                    errors.append(f"Error syncing HubspotTempData for contact {contact.get('id', 'unknown')}: {str(e)}")
                    continue
            
            # for contact in filtered_contacts:
            #     try:
            #         contact_data = extract_contact_data(contact)
                    
            #         # Check if contact exists
            #         existing_contact = None
            #         if contact_data['email']:
            #             existing_contact = await prisma_service.get_contact_by_email(contact_data['email'])
                    
            #         if not existing_contact and contact_data['hubspot_id']:
            #             existing_contact = await prisma_service.get_contact_by_hubspot_id(contact_data['hubspot_id'])
                    
            #         if existing_contact:
            #             await prisma_service.update_contact(existing_contact.id, contact_data)
            #         else:
            #             await prisma_service.create_contact(contact_data)
                    
            #         synced_count += 1
                    
            #     except Exception as e:
            #         error_msg = f"Error processing contact {contact.get('id', 'unknown')}: {str(e)}"
            #         errors.append(error_msg)
            #         logger.error(error_msg)
            
            return {
                "status": "success",
                "message": f"Manual sync completed",
                "total_fetched": len(contacts),
                "total_filtered": len(filtered_contacts),
                "synced_count": synced_temp_count,
                "errors_count": len(errors),
                "errors": errors[:10]  # Return first 10 errors
            }
            
        finally:
            await prisma_service.disconnect()
            
    except Exception as e:
        logger.error(f"Error in manual sync: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    try:
        logger.info("Starting uvicorn server")
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