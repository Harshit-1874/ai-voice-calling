#!/usr/bin/env python3
"""
Test script to verify transcription saving functionality
"""

import asyncio
import logging
from services.prisma_service import PrismaService
from services.websocket_service import WebSocketService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_transcription_saving():
    """Test transcription saving functionality"""
    try:
        # Initialize services
        prisma_service = PrismaService()
        websocket_service = WebSocketService()
        
        # Test call_sid
        test_call_sid = "test_call_123"
        
        logger.info("="*50)
        logger.info("Testing transcription saving functionality")
        logger.info("="*50)
        
        # 1. Create a test call log
        async with prisma_service:
            call_log = await prisma_service.create_call_log(
                call_sid=test_call_sid,
                from_number="+1234567890",
                to_number="+0987654321",
                status="completed"
            )
            logger.info(f"Created test call log with ID: {call_log.id}")
        
        # 2. Test direct transcription saving
        logger.info("Testing direct transcription saving...")
        await websocket_service.save_transcription_to_database(
            call_sid=test_call_sid,
            speaker="user",
            text="Hello, this is a test transcription",
            confidence=0.95
        )
        
        await websocket_service.save_transcription_to_database(
            call_sid=test_call_sid,
            speaker="assistant",
            text="Hi! This is a test response",
            confidence=0.98
        )
        
        # 3. Test transcription buffer
        logger.info("Testing transcription buffer...")
        buffer = await websocket_service.get_or_create_transcription_buffer(test_call_sid)
        
        # Add transcriptions to buffer
        buffer.add_transcription("user", "This is a buffer test", 0.92)
        buffer.add_transcription("assistant", "This is a buffer response", 0.94)
        
        logger.info(f"Buffer has {buffer.get_transcription_count()} transcriptions")
        
        # 4. Test buffer flush to database
        logger.info("Testing buffer flush to database...")
        await buffer.flush_to_database(prisma_service)
        
        # 5. Verify transcriptions in database
        logger.info("Verifying transcriptions in database...")
        async with prisma_service:
            transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
            logger.info(f"Found {len(transcriptions)} transcriptions in database")
            
            for i, t in enumerate(transcriptions):
                logger.info(f"Transcription {i+1}: {t.speaker} - {t.text}")
        
        # 6. Test transcription service
        logger.info("Testing transcription service...")
        transcription_service = websocket_service.get_transcription_service()
        transcription_service.start_call_transcription(test_call_sid)
        
        transcription_service.add_transcription_entry(
            call_sid=test_call_sid,
            speaker="user",
            text="Service test user message",
            confidence=0.91
        )
        
        transcription_service.add_transcription_entry(
            call_sid=test_call_sid,
            speaker="assistant", 
            text="Service test assistant response",
            confidence=0.93
        )
        
        # End transcription
        completed_transcription = await transcription_service.end_call_transcription(test_call_sid)
        if completed_transcription:
            logger.info(f"Completed transcription with {len(completed_transcription.entries)} entries")
        
        logger.info("="*50)
        logger.info("Test completed successfully!")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_transcription_saving()) 