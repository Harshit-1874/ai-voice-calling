#!/usr/bin/env python3
"""
Simple script to test Twilio Record-based Transcription functionality
"""

import asyncio
import json
from services.prisma_service import PrismaService
from services.twilio_service import TwilioService

async def test_transcription_setup():
    """Test that our transcription setup is working correctly"""
    print("Testing Twilio Record-based Transcription Setup...")
    
    # Test TwiML generation
    twilio_service = TwilioService()
    
    # Test creating TwiML with recording and transcription
    twiml = twilio_service.create_twiml_response(
        ws_host="test-host.ngrok.io",
        from_number="+1234567890",
        to_number="+0987654321",
        call_sid="TEST_CALL_SID_12345"
    )
    
    print("\nGenerated TwiML:")
    print(twiml)
    print("\n" + "="*50)
    
    # Test database connection and transcription storage
    prisma_service = PrismaService()
    
    try:
        async with prisma_service:
            print("Database connection successful!")
            
            # Test creating a sample call log
            test_call_sid = "TEST_CALL_SID_12345"
            
            # Check if test call already exists
            existing_call = await prisma_service.get_call_log(test_call_sid)
            if existing_call:
                print(f"Test call log already exists: {existing_call.id}")
                call_log_id = existing_call.id
            else:
                # Create test call log
                call_log = await prisma_service.create_call_log(
                    call_sid=test_call_sid,
                    from_number="+1234567890",
                    to_number="+0987654321",
                    status="in-progress"
                )
                call_log_id = call_log.id
                print(f"Created test call log: {call_log_id}")
            
            # Test storing transcription (simulating what the callback would do)
            transcription = await prisma_service.prisma.transcription.create({
                "callLogId": call_log_id,
                "sessionId": "RE_TEST_RECORDING_SID",  # Recording SID instead of transcription SID
                "speaker": "both",  # Record captures both sides
                "text": "Hello, I'm interested in your payment solutions. Can you tell me more about Teya's services?",
                "confidence": 0.89,
                "isFinal": True
            })
            print(f"Created test transcription: {transcription.id}")
            
            # Test retrieving transcriptions
            transcriptions = await prisma_service.get_transcriptions_for_call(call_log_id)
            print(f"Retrieved {len(transcriptions)} transcriptions for call")
            
            for t in transcriptions:
                print(f"  - {t.speaker}: {t.text} (confidence: {t.confidence})")
            
            # Test conversation analysis
            try:
                conversation = await prisma_service.create_conversation_analysis(
                    call_log_id=call_log_id,
                    summary="Customer inquiry about payment solutions",
                    key_points=["interested in payment solutions", "asked about Teya services"],
                    sentiment="positive",
                    lead_score=8,
                    next_action="Follow up with product demo"
                )
                print(f"Created conversation analysis: {conversation.id}")
            except Exception as e:
                print(f"Note: Conversation analysis creation failed (this is optional): {str(e)}")
            
            print("\nRecord-based transcription test completed successfully!")
            
    except Exception as e:
        print(f"Error during database test: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_transcription_setup())
