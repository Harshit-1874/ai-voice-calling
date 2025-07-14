#!/usr/bin/env python3
"""
Test script to verify JSON transcription saving with updated call controller
"""

import asyncio
import logging
from services.prisma_service import PrismaService
from services.websocket_service import WebSocketService
from controllers.call_controller import CallController
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_json_saving():
    """Test JSON transcription saving with updated call controller"""
    try:
        # Initialize services
        prisma_service = PrismaService()
        websocket_service = WebSocketService()
        call_controller = CallController()
        
        # Test call_sid
        test_call_sid = "test_json_saving_999"
        
        logger.info("="*50)
        logger.info("Testing JSON transcription saving with updated call controller")
        logger.info("="*50)
        
        # 1. Create a test call log
        async with prisma_service:
            call_log = await prisma_service.create_call_log(
                call_sid=test_call_sid,
                from_number="+1234567890",
                to_number="+0987654321",
                status="completed"
            )
            logger.info(f"Created call log with ID: {call_log.id}")
        
        # 2. Add transcriptions to the buffer
        logger.info("Adding transcriptions to buffer...")
        buffer = await websocket_service.get_or_create_transcription_buffer(test_call_sid)
        
        # Set up the buffer with call_log_id
        buffer.set_session_info("test_session", call_log.id)
        
        # Add some test transcriptions
        test_transcriptions = [
            ("user", "Hello, this is a test call"),
            ("assistant", "Hi there! How can I help you today?"),
            ("user", "I'm testing the JSON transcription saving"),
            ("assistant", "That sounds great! Let me know if you need anything."),
            ("user", "Perfect, thank you!")
        ]
        
        for speaker, text in test_transcriptions:
            buffer.add_transcription(speaker, text)
            logger.info(f"Added {speaker}: {text}")
        
        logger.info(f"Buffer now contains {buffer.get_transcription_count()} transcriptions")
        
        # 3. Test the save_call_transcriptions method
        logger.info("Testing save_call_transcriptions method...")
        result = await call_controller.save_call_transcriptions(test_call_sid)
        logger.info(f"Save result: {result}")
        
        # 4. Verify the results
        async with prisma_service:
            # Check if conversation JSON was saved
            updated_call_log = await prisma_service.get_call_log(test_call_sid)
            if updated_call_log and updated_call_log.conversationJson:
                logger.info("✅ Conversation JSON was saved successfully!")
                try:
                    json_data = json.loads(updated_call_log.conversationJson)
                    logger.info(f"✅ JSON contains {len(json_data)} entries")
                    logger.info(f"✅ JSON format: {json_data[0] if json_data else 'No entries'}")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON: {e}")
            else:
                logger.warning("❌ No conversation JSON found")
            
            # Check individual transcriptions
            transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
            logger.info(f"Individual transcriptions: {len(transcriptions)}")
        
        logger.info("="*50)
        logger.info("Test completed!")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_json_saving()) 