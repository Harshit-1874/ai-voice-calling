#!/usr/bin/env python3
"""
Test script for transcription buffer functionality.
"""

import asyncio
import logging
from services.websocket_service import WebSocketService
from services.prisma_service import PrismaService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_transcription_buffer():
    """Test the transcription buffer functionality."""
    try:
        # Initialize services
        websocket_service = WebSocketService()
        prisma_service = PrismaService()
        
        call_sid = "test_buffer_call_123"
        
        logger.info(f"Testing transcription buffer for call: {call_sid}")
        
        # Test 1: Create a call log first
        async with prisma_service:
            call_log = await prisma_service.create_call_log(
                call_sid=call_sid,
                from_number="+1234567890",
                to_number="+0987654321",
                status="initiated"
            )
            logger.info(f"Created call log with ID: {call_log.id}")
        
        # Test 2: Get or create buffer
        buffer = websocket_service.get_or_create_transcription_buffer(call_sid)
        logger.info(f"Buffer created/retrieved for call {call_sid}")
        
        # Test 3: Add transcriptions to buffer
        buffer.add_transcription(
            speaker="user",
            text="Hello, this is a test call",
            confidence=0.95
        )
        
        buffer.add_transcription(
            speaker="assistant",
            text="Hello! I'm calling from Teya UK. How can I help you today?",
            confidence=0.98
        )
        
        buffer.add_transcription(
            speaker="user",
            text="I'm interested in your payment solutions",
            confidence=0.92
        )
        
        logger.info(f"Added {buffer.get_transcription_count()} transcriptions to buffer")
        
        # Test 4: Set session info
        buffer.set_session_info("test_session_123", call_log.id)
        logger.info("Set session info in buffer")
        
        # Test 5: Save to database
        await buffer.flush_to_database(prisma_service)
        logger.info("Flushed buffer to database")
        
        # Test 6: Verify in database
        async with prisma_service:
            saved_transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
            logger.info(f"Found {len(saved_transcriptions)} transcriptions in database")
            
            for i, t in enumerate(saved_transcriptions):
                logger.info(f"DB Transcription {i+1}: {t.speaker} - {t.text[:50]}... (confidence: {t.confidence})")
        
        logger.info("Transcription buffer test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in transcription buffer test: {str(e)}")
        raise

async def main():
    """Main test function."""
    logger.info("Starting transcription buffer tests...")
    
    try:
        await test_transcription_buffer()
        logger.info("All transcription buffer tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 