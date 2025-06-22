# routes/queue_routes.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from services.queue_service import QueueService
from services.prisma_service import PrismaService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/queue", tags=["Queue Management"])

# Pydantic models for request/response
class ContactCallRequest(BaseModel):
    contact_id: str
    phone: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    priority: Optional[int] = 5
    delay: Optional[int] = 0

class BatchCallRequest(BaseModel):
    contact_ids: List[str]
    batch_size: Optional[int] = 5
    delay_between_calls: Optional[int] = 30

class QueueStatsResponse(BaseModel):
    active_calls: int
    queued_tasks: int
    batch_tasks: int
    error_records: int
    timestamp: str

@router.post("/call/single")
async def queue_single_call(request: ContactCallRequest):
    """
    Queue a single call for a contact
    """
    try:
        logger.info(f"Queueing single call for contact: {request.contact_id}")
        
        queue_service = QueueService()
        
        # Prepare contact data
        contact_data = {
            'hubspotId': request.contact_id,
            'phone': request.phone,
            'email': request.email,
            'firstName': request.first_name,
            'lastName': request.last_name
        }
        
        # Queue the call
        task_id = queue_service.queue_single_call(
            contact_data=contact_data,
            delay=request.delay,
            priority=request.priority
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Call queued successfully",
                "task_id": task_id,
                "contact_id": request.contact_id,
                "priority": request.priority,
                "delay": request.delay
            }
        )
        
    except Exception as e:
        logger.error(f"Error queueing single call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/call/batch")
async def queue_batch_calls(request: BatchCallRequest):
    """
    Queue batch calls for multiple contacts
    """
    try:
        logger.info(f"Queueing batch calls for {len(request.contact_ids)} contacts")
        
        prisma_service = PrismaService()
        queue_service = QueueService()
        
        # Fetch contact data from database
        contacts = []
        async with prisma_service:
            for contact_id in request.contact_ids:
                try:
                    contact = await prisma_service.get_hubspot_temp_data_by_id(contact_id)
                    if contact:
                        contacts.append({
                            'hubspotId': contact.hubspotId,
                            'email': contact.email,
                            'phone': contact.phone,
                            'firstName': contact.firstName,
                            'lastName': contact.lastName,
                            'hsLeadStatus': contact.hsLeadStatus
                        })
                    else:
                        logger.warning(f"Contact not found: {contact_id}")
                except Exception as e:
                    logger.error(f"Error fetching contact {contact_id}: {str(e)}")
                    continue
        
        if not contacts:
            raise HTTPException(status_code=400, detail="No valid contacts found")
        
        # Queue the batch
        batch_task_id = queue_service.queue_batch_calls(
            contacts=contacts,
            batch_size=request.batch_size,
            delay_between_calls=request.delay_between_calls
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Batch calls queued successfully",
                "batch_task_id": batch_task_id,
                "total_contacts": len(contacts),
                "batch_size": request.batch_size,
                "delay_between_calls": request.delay_between_calls
            }
        )
        
    except Exception as e:
        logger.error(f"Error queueing batch calls: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_queue_stats():
    """
    Get queue statistics
    """
    try:
        queue_service = QueueService()
        stats = queue_service.get_queue_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "stats": stats
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting queue stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status of a specific task
    """
    try:
        queue_service = QueueService()
        status = queue_service.get_task_status(task_id)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "task_status": status
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a queued task
    """
    try:
        queue_service = QueueService()
        success = queue_service.cancel_task(task_id)
        
        if success:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": f"Task {task_id} cancelled successfully"
                }
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to cancel task")
            
    except Exception as e:
        logger.error(f"Error cancelling task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calls/recent")
async def get_recent_calls(limit: int = 50):
    """
    Get recent calls from the queue system
    """
    try:
        queue_service = QueueService()
        calls = queue_service.get_recent_calls(limit)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "calls": calls,
                "total": len(calls)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting recent calls: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/errors")
async def get_call_errors(limit: int = 20):
    """
    Get recent call errors
    """
    try:
        queue_service = QueueService()
        errors = queue_service.get_call_errors(limit)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "errors": errors,
                "total": len(errors)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting call errors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def schedule_cleanup():
    """
    Schedule cleanup of old call data
    """
    try:
        queue_service = QueueService()
        task_id = queue_service.schedule_cleanup()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Cleanup scheduled successfully",
                "cleanup_task_id": task_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error scheduling cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-and-queue")
async def trigger_sync_and_queue(background_tasks: BackgroundTasks):
    """
    Trigger HubSpot sync and queue calls manually
    """
    try:
        # Import here to avoid circular imports
        from hubspot_cron_sync import sync_hubspot_contacts
        
        # Add the sync task to background tasks
        background_tasks.add_task(sync_hubspot_contacts)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "HubSpot sync and call queuing triggered successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"Error triggering sync and queue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def queue_health_check():
    """
    Health check for the queue system
    """
    try:
        queue_service = QueueService()
        
        # Test Redis connection
        redis_connected = False
        try:
            queue_service.redis_service.client.ping()
            redis_connected = True
        except Exception:
            pass
        
        # Test Celery
        celery_connected = False
        try:
            from celery_app import celery_app
            celery_app.control.inspect().ping()
            celery_connected = True
        except Exception:
            pass
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "redis_connected": redis_connected,
                "celery_connected": celery_connected,
                "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
                    "health", 0, "", 0, "", (), None
                )) if logger.handlers else "N/A"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))