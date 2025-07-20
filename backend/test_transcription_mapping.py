#!/usr/bin/env python3
"""
Test script to verify call_sid mapping and transcription saving
"""

import asyncio
import logging
from services.websocket_service import WebSocketService
from services.prisma_service import PrismaService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_call_sid_mapping():
    """Test call_sid mapping and transcription saving"""
    
    websocket_service = WebSocketService()
    prisma_service = PrismaService()
    
    # Test call_sids
    temp_call_sid = "temp_call_123"
    real_call_sid = "CA3b4c9c252242c97308a4ed189101b19c"
    
    print("="*50)
    print("Testing Call SID Mapping and Transcription Saving")
    print("="*50)
    
    # Test 1: Create transcription buffer with temp call_sid
    print("\n1. Creating transcription buffer with temp call_sid...")
    buffer = websocket_service.get_or_create_transcription_buffer(temp_call_sid)
    print(f"Buffer created with {buffer.get_transcription_count()} transcriptions")
    
    # Test 2: Add some test transcriptions
    print("\n2. Adding test transcriptions...")
    buffer.add_transcription("user", "Hello, this is a test call", 0.95)
    buffer.add_transcription("assistant", "Hi there! How can I help you today?", 0.98)
    buffer.add_transcription("user", "I'm interested in your services", 0.92)
    print(f"Buffer now has {buffer.get_transcription_count()} transcriptions")
    
    # Test 3: Map temp call_sid to real call_sid
    print("\n3. Mapping temp call_sid to real call_sid...")
    websocket_service.map_temp_to_real_call_sid(temp_call_sid, real_call_sid)
    print(f"Mapped {temp_call_sid} -> {real_call_sid}")
    
    # Test 4: Verify buffer was moved
    print("\n4. Verifying buffer was moved...")
    if real_call_sid in websocket_service.transcription_buffers:
        moved_buffer = websocket_service.transcription_buffers[real_call_sid]
        print(f"Buffer moved successfully with {moved_buffer.get_transcription_count()} transcriptions")
    else:
        print("ERROR: Buffer was not moved!")
    
    # Test 5: Test database saving with real call_sid
    print("\n5. Testing database saving with real call_sid...")
    try:
        async with prisma_service:
            # Create a test call log
            call_log = await prisma_service.create_call_log(
                call_sid=real_call_sid,
                from_number="+1234567890",
                to_number="+0987654321",
                status="test"
            )
            print(f"Created test call log with ID: {call_log.id}")
            
            # Set session info in buffer
            moved_buffer.set_session_info("test_session", call_log.id)
            
            # Save transcriptions
            await moved_buffer.flush_to_database(prisma_service)
            print("Transcriptions saved to database")
            
            # Verify transcriptions were saved
            saved_transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
            print(f"Found {len(saved_transcriptions)} transcriptions in database")
            
            for t in saved_transcriptions:
                print(f"  - {t.speaker}: {t.text[:50]}... (confidence: {t.confidence})")
                
    except Exception as e:
        print(f"Error testing database saving: {str(e)}")
    
    # Test 6: Test finalize_call_transcriptions with mapping
    print("\n6. Testing finalize_call_transcriptions with mapping...")
    try:
        await websocket_service.finalize_call_transcriptions(real_call_sid)
        print("Successfully finalized transcriptions with mapping")
    except Exception as e:
        print(f"Error finalizing transcriptions: {str(e)}")
    
    print("\n" + "="*50)
    print("Test completed!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(test_call_sid_mapping()) 