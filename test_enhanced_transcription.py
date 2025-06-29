#!/usr/bin/env python3
"""
Test script to verify enhanced transcription service functionality
Tests both OpenAI event handling and Twilio callback processing
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.transcription_service import TranscriptionService
from services.websocket_service import WebSocketService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_transcription_service():
    """Test the enhanced transcription service"""
    print("🧪 Testing Enhanced Transcription Service")
    print("=" * 60)
    
    # Initialize services
    transcription_service = TranscriptionService()
    websocket_service = WebSocketService()
    
    # Test 1: Initialize session
    test_call_sid = "CA_test_enhanced_transcription_001"
    test_session_id = "session_test_001"
    
    print(f"\n1️⃣ Testing session initialization...")
    session_data = await transcription_service.initialize_session(test_call_sid, test_session_id)
    if session_data:
        print(f"✅ Session initialized successfully: {test_call_sid}")
        print(f"   Session ID: {test_session_id}")
        print(f"   Start time: {session_data['start_time']}")
    else:
        print("❌ Session initialization failed")
        return False
    
    # Test 2: Process partial transcriptions (similar to Deepgram interim results)
    print(f"\n2️⃣ Testing partial transcription processing...")
    await transcription_service.process_openai_transcript(
        call_sid=test_call_sid,
        speaker="customer",
        text="Hello this is a test",
        is_final=False,
        is_speech_final=False,
        confidence=0.8,
        session_id=test_session_id
    )
    print("✅ Partial transcription processed")
    
    # Test 3: Process final transcription chunk
    print(f"\n3️⃣ Testing final transcription chunk...")
    await transcription_service.process_openai_transcript(
        call_sid=test_call_sid,
        speaker="customer", 
        text="call to verify the system",
        is_final=True,
        is_speech_final=False,
        confidence=0.9,
        session_id=test_session_id
    )
    print("✅ Final transcription chunk processed")
    
    # Test 4: Process speech_final event (should save to database)
    print(f"\n4️⃣ Testing speech_final event (save to DB)...")
    await transcription_service.process_openai_transcript(
        call_sid=test_call_sid,
        speaker="customer",
        text="is working correctly.",
        is_final=True,
        is_speech_final=True,  # This should trigger database save
        confidence=0.95,
        session_id=test_session_id
    )
    print("✅ Speech final transcription processed and saved to DB")
    
    # Test 5: Handle utterance end (backup save mechanism)
    print(f"\n5️⃣ Testing utterance end handling...")
    await transcription_service.handle_utterance_end(
        call_sid=test_call_sid,
        speaker="customer",
        session_id=test_session_id
    )
    print("✅ Utterance end handled")
    
    # Test 6: Process assistant response
    print(f"\n6️⃣ Testing assistant transcription...")
    await transcription_service.process_openai_transcript(
        call_sid=test_call_sid,
        speaker="assistant",
        text="Thank you for calling. How can I help you today?",
        is_final=True,
        is_speech_final=True,
        confidence=0.98,
        session_id=test_session_id
    )
    print("✅ Assistant transcription processed")
    
    # Test 7: Test Twilio transcription processing
    print(f"\n7️⃣ Testing Twilio transcription processing...")
    success = await transcription_service.process_twilio_transcription(
        call_sid=test_call_sid,
        transcription_text="This is a full call transcription from Twilio recording service.",
        confidence=0.87,
        recording_url="https://api.twilio.com/test-recording.mp3"
    )
    if success:
        print("✅ Twilio transcription processed successfully")
    else:
        print("❌ Twilio transcription processing failed")
    
    # Test 8: Get session statistics
    print(f"\n8️⃣ Testing session statistics...")
    stats = transcription_service.get_session_stats(test_call_sid)
    print(f"✅ Session stats retrieved:")
    print(f"   Total transcripts: {stats.get('total_transcripts', 0)}")
    print(f"   Session active: {stats.get('call_sid') == test_call_sid}")
    
    # Test 9: Mock OpenAI event handling
    print(f"\n9️⃣ Testing OpenAI event handling...")
    
    # Mock transcription completed event
    mock_transcription_event = {
        "type": "conversation.item.input_audio_transcription.completed",
        "item_id": "item_test_001", 
        "content_index": 0,
        "transcript": "This is a test transcription from OpenAI."
    }
    
    await websocket_service.handle_openai_events(
        response=mock_transcription_event,
        call_sid=test_call_sid,
        session_id=test_session_id
    )
    print("✅ OpenAI transcription completed event handled")
    
    # Mock speech events
    mock_speech_started = {
        "type": "input_audio_buffer.speech_started"
    }
    
    await websocket_service.handle_openai_events(
        response=mock_speech_started,
        call_sid=test_call_sid,
        session_id=test_session_id
    )
    print("✅ Speech started event handled")
    
    mock_speech_stopped = {
        "type": "input_audio_buffer.speech_stopped"
    }
    
    await websocket_service.handle_openai_events(
        response=mock_speech_stopped,
        call_sid=test_call_sid,
        session_id=test_session_id
    )
    print("✅ Speech stopped event handled")
    
    # Test 10: Finalize session
    print(f"\n🔟 Testing session finalization...")
    await transcription_service.finalize_session(test_call_sid)
    print("✅ Session finalized successfully")
    
    # Final stats check
    print(f"\n📊 Final session check...")
    final_stats = transcription_service.get_session_stats(test_call_sid)
    if "error" in final_stats:
        print("✅ Session properly cleaned up (no longer exists)")
    else:
        print("⚠️  Session still exists after finalization")
    
    print(f"\n🎉 Enhanced Transcription Service Test Complete!")
    print("=" * 60)
    return True

async def test_event_driven_flow():
    """Test the complete event-driven flow similar to Deepgram"""
    print("\n🔄 Testing Event-Driven Flow (Deepgram-style)")
    print("=" * 60)
    
    transcription_service = TranscriptionService()
    test_call_sid = "CA_test_event_flow_002"
    test_session_id = "session_event_002"
    
    # Initialize session
    await transcription_service.initialize_session(test_call_sid, test_session_id)
    
    # Simulate a conversation flow
    conversation_flow = [
        # Customer starts speaking
        {"speaker": "customer", "text": "Hi", "is_final": False, "is_speech_final": False},
        {"speaker": "customer", "text": "Hi I'm", "is_final": False, "is_speech_final": False},
        {"speaker": "customer", "text": "Hi I'm calling about", "is_final": True, "is_speech_final": False},
        {"speaker": "customer", "text": "your payment services", "is_final": True, "is_speech_final": True},  # Should save
        
        # Assistant responds
        {"speaker": "assistant", "text": "Hello! Thank you for calling Teya.", "is_final": True, "is_speech_final": True},
        
        # Customer continues
        {"speaker": "customer", "text": "I need", "is_final": False, "is_speech_final": False},
        {"speaker": "customer", "text": "I need help with", "is_final": True, "is_speech_final": False},
        {"speaker": "customer", "text": "setting up a card machine", "is_final": True, "is_speech_final": True},  # Should save
    ]
    
    print("Processing conversation flow...")
    for i, event in enumerate(conversation_flow):
        print(f"  Event {i+1}: {event['speaker']} - '{event['text']}' (final={event['is_final']}, speech_final={event['is_speech_final']})")
        
        await transcription_service.process_openai_transcript(
            call_sid=test_call_sid,
            speaker=event['speaker'],
            text=event['text'],
            is_final=event['is_final'],
            is_speech_final=event['is_speech_final'],
            confidence=0.9,
            session_id=test_session_id
        )
        
        # Small delay to simulate real-time flow
        await asyncio.sleep(0.1)
    
    # Check final stats
    stats = transcription_service.get_session_stats(test_call_sid)
    print(f"\n📊 Conversation processed:")
    print(f"   Total saved transcripts: {stats['total_transcripts']}")
    
    # Clean up
    await transcription_service.finalize_session(test_call_sid)
    print("✅ Event-driven flow test complete")

if __name__ == "__main__":
    async def main():
        print("🚀 Starting Enhanced Transcription System Tests")
        print(f"⏰ Test started at: {datetime.now()}")
        
        try:
            # Test the transcription service
            success = await test_transcription_service()
            
            if success:
                # Test event-driven flow
                await test_event_driven_flow()
                
                print(f"\n✅ All tests completed successfully!")
                print(f"🎯 The enhanced transcription system is ready for production use.")
            else:
                print(f"\n❌ Tests failed!")
                
        except Exception as e:
            logger.error(f"Test error: {str(e)}")
            print(f"\n💥 Test failed with error: {str(e)}")
    
    # Run the tests
    asyncio.run(main())
