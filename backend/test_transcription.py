#!/usr/bin/env python3
"""
Test script for the new transcription implementation.
This script tests the transcription service functionality.
"""

import asyncio
import logging
from datetime import datetime
from services.transcription_service import TranscriptionService, SpeakerType
from services.prisma_service import PrismaService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_transcription_service():
    """Test the transcription service functionality."""
    try:
        # Initialize services
        prisma_service = PrismaService()
        transcription_service = TranscriptionService(prisma_service)
        
        logger.info("Testing transcription service...")
        
        # Test 1: Start a call transcription
        call_sid = "test_call_123"
        transcription = transcription_service.start_call_transcription(call_sid)
        logger.info(f"Started transcription for call: {call_sid}")
        
        # Test 2: Add some transcription entries
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
        
        # Test 3: End the transcription and save to database
        completed_transcription = await transcription_service.end_call_transcription(call_sid)
        logger.info(f"Ended transcription. Duration: {completed_transcription.total_duration:.2f} seconds")
        
        # Test 4: Get confidence scores
        confidence_scores = await transcription_service.get_call_confidence_score(call_sid)
        logger.info(f"Confidence scores: {confidence_scores}")
        
        # Test 5: Get transcription from database
        db_transcription = await transcription_service.get_call_transcription_from_db(call_sid)
        if db_transcription:
            logger.info(f"Retrieved transcription from database with {len(db_transcription.get('entries', []))} entries")
        
        # Test 6: Get previous call context (this will be empty for test data)
        context = await transcription_service.get_previous_call_context("+1234567890")
        logger.info(f"Previous call context: {context[:100]}..." if context else "No previous context found")
        
        logger.info("All transcription tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in transcription test: {str(e)}")
        raise

async def test_prisma_service():
    """Test the Prisma service functionality."""
    try:
        prisma_service = PrismaService()
        
        logger.info("Testing Prisma service...")
        
        # Test 1: Get call statistics
        stats = await prisma_service.get_call_statistics()
        logger.info(f"Call statistics: {stats}")
        
        # Test 2: Get all call logs
        call_logs = await prisma_service.get_all_call_logs(limit=5)
        logger.info(f"Found {len(call_logs)} call logs")
        
        # Test 3: Get calls by phone number
        if call_logs:
            phone_number = call_logs[0].toNumber
            calls_by_phone = await prisma_service.get_calls_by_phone_number(phone_number)
            logger.info(f"Found {len(calls_by_phone)} calls for {phone_number}")
        
        logger.info("All Prisma tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in Prisma test: {str(e)}")
        raise

async def main():
    """Main test function."""
    logger.info("Starting transcription system tests...")
    
    try:
        await test_prisma_service()
        await test_transcription_service()
        logger.info("All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 