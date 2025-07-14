#!/usr/bin/env python3
"""
Test script to debug transcription buffer management
"""

import asyncio
import logging
from services.prisma_service import PrismaService
from services.websocket_service import WebSocketService

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_buffer_debug():
    """Test buffer management debugging"""
    try:
        # Initialize services
        prisma_service = PrismaService()
        websocket_service = WebSocketService()
        
        # Test call_sid
        test_call_sid = "test_buffer_debug_789"
        
        logger.info("="*50)
        logger.info("Testing buffer management debugging")
        logger.info("="*50)
        
        # 1. Create a test call log
        async with prisma_service:
            call_log = await prisma_service.create_call_log(
                call_sid=test_call_sid,
                from_number="+1234567890",
                to_number="+0987654321",
                status="initiated"
            )
            logger.info(f"Created call log with ID: {call_log.id}")
        
        # 2. Test buffer creation
        logger.info("Testing buffer creation...")
        buffer = await websocket_service.get_or_create_transcription_buffer(test_call_sid)
        logger.info(f"Buffer created with {buffer.get_transcription_count()} transcriptions")
        logger.info(f"Available buffers: {list(websocket_service.transcription_buffers.keys())}")
        
        # 3. Add some transcriptions
        logger.info("Adding transcriptions to buffer...")
        buffer.add_transcription("user", "Hello, this is a test")
        buffer.add_transcription("assistant", "Hi there! How can I help you?")
        buffer.add_transcription("user", "I need some assistance")
        
        logger.info(f"Buffer now has {buffer.get_transcription_count()} transcriptions")
        logger.info(f"Available buffers: {list(websocket_service.transcription_buffers.keys())}")
        
        # 4. Test finalization
        logger.info("Testing finalization...")
        await websocket_service.finalize_call_transcriptions(test_call_sid)
        
        # 5. Check if transcriptions were saved
        async with prisma_service:
            call_log = await prisma_service.get_call_log(test_call_sid)
            if call_log:
                transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
                logger.info(f"Found {len(transcriptions)} transcriptions in database")
                for t in transcriptions:
                    logger.info(f"Transcription: {t.speaker} - {t.text}")
            else:
                logger.warning("Call log not found")
        
        logger.info("="*50)
        logger.info("Test completed")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_buffer_debug()) 