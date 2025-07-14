#!/usr/bin/env python3
"""
Test script to verify JSON-based transcription saving functionality
"""

import asyncio
import logging
import json
from services.prisma_service import PrismaService
from services.websocket_service import WebSocketService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_json_transcription_saving():
    """Test JSON-based transcription saving functionality"""
    try:
        # Initialize services
        prisma_service = PrismaService()
        websocket_service = WebSocketService()
        
        # Test call_sid
        test_call_sid = "test_json_call_456"
        
        logger.info("="*50)
        logger.info("Testing JSON-based transcription saving")
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
        
        # 2. Create a transcription buffer and add transcriptions
        logger.info("Creating transcription buffer and adding transcriptions...")
        buffer = await websocket_service.get_or_create_transcription_buffer(test_call_sid)
        
        # Add sample transcriptions (similar to your example)
        sample_transcriptions = [
            {
                "speaker": "assistant",
                "text": "Hi! Sure, I'd be happy to share. We run a small café in the city centre. We've been around for about five years now.",
                "confidence": None,
                "timestamp": "2025-07-11T02:47:41.146888",
                "is_final": True
            },
            {
                "speaker": "user", 
                "text": "I'm doing this.",
                "confidence": None,
                "timestamp": "2025-07-11T02:47:51.814317",
                "is_final": True
            },
            {
                "speaker": "user",
                "text": "to test if the transcription is being saved in my local database.",
                "confidence": None,
                "timestamp": "2025-07-11T02:47:54.358779",
                "is_final": True
            },
            {
                "speaker": "assistant",
                "text": "Alright, that makes sense. Now, in your café, how are you currently handling payments from your customers?",
                "confidence": None,
                "timestamp": "2025-07-11T02:47:55.083796",
                "is_final": True
            },
            {
                "speaker": "user",
                "text": "Okay, bye.",
                "confidence": None,
                "timestamp": "2025-07-11T02:48:04.034998",
                "is_final": True
            }
        ]
        
        # Add transcriptions to buffer
        for transcription in sample_transcriptions:
            buffer.add_transcription(
                speaker=transcription["speaker"],
                text=transcription["text"],
                confidence=transcription["confidence"]
            )
        
        logger.info(f"Added {len(sample_transcriptions)} transcriptions to buffer")
        logger.info(f"Buffer has {buffer.get_transcription_count()} transcriptions")
        
        # 3. Test buffer flush to database (this should save as single JSON entry)
        logger.info("Testing buffer flush to database...")
        await buffer.flush_to_database(prisma_service)
        
        # 4. Verify the JSON entry in database
        logger.info("Verifying JSON entry in database...")
        async with prisma_service:
            transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
            logger.info(f"Found {len(transcriptions)} transcription entries in database")
            
            for i, t in enumerate(transcriptions):
                logger.info(f"Transcription entry {i+1}:")
                logger.info(f"  Speaker: {t.speaker}")
                logger.info(f"  Text length: {len(t.text)} characters")
                logger.info(f"  Is JSON: {t.speaker == 'conversation'}")
                
                if t.speaker == "conversation":
                    try:
                        # Parse the JSON conversation
                        conversation_data = json.loads(t.text)
                        logger.info(f"  JSON conversation contains {len(conversation_data)} entries:")
                        
                        for j, entry in enumerate(conversation_data):
                            logger.info(f"    Entry {j+1}: {entry['speaker']} - {entry['text'][:50]}...")
                        
                        # Verify the JSON structure matches your format
                        expected_keys = ["speaker", "text", "confidence", "timestamp", "is_final"]
                        if all(key in conversation_data[0] for key in expected_keys):
                            logger.info("  ✅ JSON structure matches expected format")
                        else:
                            logger.warning("  ❌ JSON structure doesn't match expected format")
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"  ❌ Failed to parse JSON: {str(e)}")
                else:
                    logger.info(f"  Text: {t.text[:100]}...")
        
        logger.info("="*50)
        logger.info("JSON transcription test completed successfully!")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_json_transcription_saving()) 