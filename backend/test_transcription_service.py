#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.transcription_service import TranscriptionService
from services.prisma_service import PrismaService

async def test_transcription_service():
    """Test the transcription service directly"""
    print("Testing TranscriptionService...")
    
    # Initialize services
    transcription_service = TranscriptionService()
    prisma_service = PrismaService()
    
    try:
        await prisma_service.connect()
        
        # Get a real call SID from recent calls
        recent_calls = await prisma_service.prisma.calllog.find_many(
            take=1,
            order={'startTime': 'desc'}
        )
        
        if not recent_calls:
            print("No recent calls found. Creating a test call first...")
            # Create a test call log
            test_call = await prisma_service.create_call_log(
                call_sid="TEST_TRANSCRIPTION_SERVICE",
                from_number="+12345678901",
                to_number="+918149190804",
                status="in-progress"
            )
            call_sid = test_call.callSid
            call_log_id = test_call.id
        else:
            call_sid = recent_calls[0].callSid
            call_log_id = recent_calls[0].id
        
        print(f"Using call SID: {call_sid}, Call Log ID: {call_log_id}")
        
        # Test 1: Initialize session
        print("\n1. Testing session initialization...")
        await transcription_service.initialize_session(call_sid, "test_session_123")
        print("✅ Session initialized successfully")
        
        # Test 2: Process OpenAI transcription event
        print("\n2. Testing OpenAI transcription processing...")
        
        result = await transcription_service.process_openai_transcript(
            call_sid=call_sid,
            speaker="user",
            text="Hello, this is a test transcription from OpenAI",
            is_final=True,
            is_speech_final=True,  # This triggers the storage
            confidence=0.9
        )
        print(f"OpenAI transcription result: {result}")
        
        # Test 3: Process Twilio transcription 
        print("\n3. Testing Twilio transcription processing...")
        twilio_result = await transcription_service.process_twilio_transcription(
            call_sid=call_sid,
            transcription_text="Hello, this is a test transcription from Twilio",
            confidence=0.95,
            recording_url="https://api.twilio.com/recordings/test.mp3"
        )
        print(f"Twilio transcription result: {twilio_result}")
        
        # Test 4: Check if transcriptions were stored
        print("\n4. Checking stored transcriptions...")
        stored_transcriptions = await prisma_service.get_transcriptions_for_call(call_log_id)
        print(f"Found {len(stored_transcriptions)} transcriptions:")
        
        for trans in stored_transcriptions:
            print(f"  - {trans.speaker}: {trans.text} (confidence: {trans.confidence})")
        
        # Test 5: Check via enhanced service
        print("\n5. Testing enhanced transcription retrieval...")
        all_transcriptions = await prisma_service.prisma.transcription.find_many(
            where={'callLogId': call_log_id},
            order={'timestamp': 'asc'}
        )
        
        print(f"Direct DB query found {len(all_transcriptions)} transcriptions:")
        for trans in all_transcriptions:
            print(f"  - ID: {trans.id}, Speaker: {trans.speaker}, Text: {trans.text[:50]}...")
        
        if len(all_transcriptions) > 0:
            print("✅ TranscriptionService is working correctly!")
        else:
            print("❌ TranscriptionService is NOT storing transcriptions properly")
            
    except Exception as e:
        print(f"Error testing transcription service: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await prisma_service.disconnect()

if __name__ == "__main__":
    asyncio.run(test_transcription_service())
