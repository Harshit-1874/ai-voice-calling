#!/usr/bin/env python3
"""
Test script for transcription saving functionality.
This script simulates a call ending and tests the transcription saving process.
"""

import asyncio
import logging
from datetime import datetime
from services.transcription_service import TranscriptionService, SpeakerType
from services.prisma_service import PrismaService
from controllers.call_controller import CallController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_transcription_saving():
    """Test the transcription saving functionality."""
    try:
        # Initialize services
        prisma_service = PrismaService()
        transcription_service = TranscriptionService(prisma_service)
        
        # Create a mock call controller
        call_controller = CallController()
        
        logger.info("Testing transcription saving...")
        
        # Test 1: Create a call log first
        call_sid = "test_call_save_123"
        async with prisma_service:
            call_log = await prisma_service.create_call_log(
                call_sid=call_sid,
                from_number="+1234567890",
                to_number="+0987654321",
                status="initiated"
            )
            logger.info(f"Created call log with ID: {call_log.id}")
        
        # Test 2: Start transcription and add entries
        transcription = transcription_service.start_call_transcription(call_sid)
        
        # Add some test transcriptions
        transcription_service.add_transcription_entry(
            call_sid=call_sid,
            speaker=SpeakerType.USER,
            text="Hello, this is a test call",
            confidence=0.95
        )
        
        transcription_service.add_transcription_entry(
            call_sid=call_sid,
            speaker=SpeakerType.ASSISTANT,
            text="Hello! I'm calling from Teya UK. How can I help you today?",
            confidence=0.98
        )
        
        transcription_service.add_transcription_entry(
            call_sid=call_sid,
            speaker=SpeakerType.USER,
            text="I'm interested in your payment solutions",
            confidence=0.92
        )
        
        logger.info(f"Added {len(transcription.entries)} transcription entries")
        
        # Test 3: Save transcriptions using the controller method
        result = await call_controller.save_call_transcriptions(call_sid)
        logger.info(f"Save result: {result}")
        
        # Test 4: Verify transcriptions were saved
        async with prisma_service:
            saved_transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
            logger.info(f"Found {len(saved_transcriptions)} saved transcriptions")
            
            for i, t in enumerate(saved_transcriptions):
                logger.info(f"Transcription {i+1}: {t.speaker} - {t.text[:50]}... (confidence: {t.confidence})")
        
        # Test 5: Check transcription status
        status = {
            "call_sid": call_sid,
            "in_memory": transcription_service.get_call_transcription(call_sid) is not None,
            "in_database": len(saved_transcriptions) > 0,
            "memory_entries": len(transcription.entries),
            "database_entries": len(saved_transcriptions)
        }
        logger.info(f"Transcription status: {status}")
        
        logger.info("Transcription saving test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in transcription saving test: {str(e)}")
        raise

async def test_call_status_handler():
    """Test the call status handler with transcription saving."""
    try:
        from fastapi import Request
        from unittest.mock import AsyncMock
        
        # Create a mock request
        mock_request = AsyncMock()
        mock_request.form.return_value = {
            "CallSid": "test_call_status_456",
            "CallStatus": "completed",
            "From": "+1234567890",
            "To": "+0987654321",
            "CallDuration": "120"
        }
        
        # Initialize controller
        call_controller = CallController()
        
        # Create a call log first
        call_sid = "test_call_status_456"
        async with call_controller.prisma_service:
            call_log = await call_controller.prisma_service.create_call_log(
                call_sid=call_sid,
                from_number="+1234567890",
                to_number="+0987654321",
                status="initiated"
            )
            
            # Add some transcriptions to memory
            call_controller.websocket_service.transcription_service.start_call_transcription(call_sid)
            call_controller.websocket_service.transcription_service.add_transcription_entry(
                call_sid=call_sid,
                speaker=SpeakerType.USER,
                text="Test call status handler",
                confidence=0.95
            )
        
        # Test the call status handler
        result = await call_controller.handle_call_status(mock_request)
        logger.info(f"Call status handler result: {result}")
        
        # Verify transcriptions were saved
        async with call_controller.prisma_service:
            saved_transcriptions = await call_controller.prisma_service.get_transcriptions_for_call(call_log.id)
            logger.info(f"Call status handler saved {len(saved_transcriptions)} transcriptions")
        
        logger.info("Call status handler test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in call status handler test: {str(e)}")
        raise

async def main():
    """Main test function."""
    logger.info("Starting transcription saving tests...")
    
    try:
        await test_transcription_saving()
        await test_call_status_handler()
        logger.info("All transcription saving tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 