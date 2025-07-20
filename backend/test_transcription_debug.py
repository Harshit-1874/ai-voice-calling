#!/usr/bin/env python3
"""
Test script to debug transcription processing
"""

import asyncio
import logging
from services.websocket_service import WebSocketService
from services.prisma_service import PrismaService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_transcription_processing():
    """Test transcription processing with mock data"""
    
    websocket_service = WebSocketService()
    prisma_service = PrismaService()
    
    # Test call_sid
    test_call_sid = "test_call_123"
    
    print("="*50)
    print("Testing Transcription Processing")
    print("="*50)
    
    # Test 1: Create transcription buffer
    print("\n1. Creating transcription buffer...")
    buffer = websocket_service.get_or_create_transcription_buffer(test_call_sid)
    print(f"Buffer created with {buffer.get_transcription_count()} transcriptions")
    
    # Test 2: Add some test transcriptions
    print("\n2. Adding test transcriptions...")
    buffer.add_transcription("user", "Hello, this is a test call", 0.95)
    buffer.add_transcription("assistant", "Hi there! How can I help you today?", 0.98)
    buffer.add_transcription("user", "I'm interested in your services", 0.92)
    print(f"Buffer now has {buffer.get_transcription_count()} transcriptions")
    
    # Test 3: Test session mapping
    print("\n3. Testing session mapping...")
    test_session_id = "session_test_123"
    websocket_service.session_to_call_mapping[test_session_id] = test_call_sid
    print(f"Session mapping: {test_session_id} -> {test_call_sid}")
    
    # Test 4: Test message processing with session mapping
    print("\n4. Testing message processing with session mapping...")
    mock_message = {
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "This is a test transcription",
        "confidence": 0.95,
        "session": {"id": test_session_id}
    }
    
    await websocket_service.process_openai_message(None, mock_message, test_session_id)
    print(f"Buffer now has {buffer.get_transcription_count()} transcriptions after processing")
    
    # Test 5: Test database saving
    print("\n5. Testing database saving...")
    try:
        async with prisma_service:
            # Create a test call log
            call_log = await prisma_service.create_call_log(
                call_sid=test_call_sid,
                from_number="+1234567890",
                to_number="+0987654321",
                status="test"
            )
            print(f"Created test call log with ID: {call_log.id}")
            
            # Set session info in buffer
            buffer.set_session_info(test_session_id, call_log.id)
            
            # Save transcriptions
            await buffer.flush_to_database(prisma_service)
            print("Transcriptions saved to database")
            
            # Verify transcriptions were saved
            saved_transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
            print(f"Found {len(saved_transcriptions)} transcriptions in database")
            
            for t in saved_transcriptions:
                print(f"  - {t.speaker}: {t.text[:50]}... (confidence: {t.confidence})")
                
    except Exception as e:
        print(f"Error testing database saving: {str(e)}")
    
    print("\n" + "="*50)
    print("Test completed!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(test_transcription_processing()) 