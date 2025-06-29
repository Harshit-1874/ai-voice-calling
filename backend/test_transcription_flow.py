#!/usr/bin/env python3
"""
Test script to debug transcription issues
"""

import asyncio
import logging
from services.prisma_service import PrismaService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_transcription_insertion():
    """Test manual transcription insertion to verify database works"""
    
    print("=== Testing Transcription Database Functionality ===")
    
    prisma_service = PrismaService()
    
    try:
        async with prisma_service:
            # First, get a recent call log
            call_logs = await prisma_service.prisma.calllog.find_many(
                order={"startTime": "desc"},
                take=1
            )
            
            if not call_logs:
                print("ERROR: No call logs found in database")
                return
            
            call_log = call_logs[0]
            print(f"Using call log: {call_log.callSid} (ID: {call_log.id})")
            
            # Test 1: Insert a test transcription
            print("\n=== Test 1: Manual Transcription Insertion ===")
            
            test_transcription = await prisma_service.prisma.transcription.create(
                data={
                    "callLogId": call_log.id,
                    "sessionId": "test_session_123",
                    "speaker": "test_user",
                    "text": "This is a test transcription to verify database functionality",
                    "confidence": 0.95,
                    "isFinal": True
                }
            )
            
            print(f"✓ Successfully created test transcription with ID: {test_transcription.id}")
            
            # Test 2: Query it back
            print("\n=== Test 2: Querying Transcription ===")
            
            retrieved = await prisma_service.prisma.transcription.find_unique(
                where={"id": test_transcription.id}
            )
            
            if retrieved:
                print(f"✓ Successfully retrieved transcription: {retrieved.text[:50]}...")
            else:
                print("✗ Failed to retrieve transcription")
            
            # Test 3: Check count
            total_count = await prisma_service.prisma.transcription.count()
            print(f"✓ Total transcriptions in database: {total_count}")
            
            # Test 4: Clean up
            print("\n=== Test 4: Cleanup ===")
            await prisma_service.prisma.transcription.delete(
                where={"id": test_transcription.id}
            )
            print("✓ Test transcription deleted")
            
            final_count = await prisma_service.prisma.transcription.count()
            print(f"✓ Final count: {final_count}")
            
            print("\n=== Database Functionality Test: PASSED ===")
            print("The database can store and retrieve transcriptions correctly.")
            print("The issue is likely in the webhook callbacks or OpenAI event handling.")
            
    except Exception as e:
        print(f"✗ Database test failed: {str(e)}")
        logger.error(f"Database test error: {str(e)}")

async def analyze_webhook_configuration():
    """Analyze the webhook configuration"""
    
    print("\n=== Webhook Configuration Analysis ===")
    
    from config import BASE_URL
    print(f"Current BASE_URL: {BASE_URL}")
    
    expected_endpoints = [
        "/recording-callback",
        "/transcription-callback",
        "/websocket"
    ]
    
    print("\nExpected webhook endpoints:")
    for endpoint in expected_endpoints:
        full_url = f"{BASE_URL.rstrip('/')}{endpoint}"
        print(f"  - {full_url}")
    
    print("\nTo check if webhooks are working:")
    print("1. Make a call through the system")
    print("2. Check server logs for incoming webhook requests")
    print("3. Look for 'POST /recording-callback' and 'POST /transcription-callback' in logs")

async def main():
    """Main debug function"""
    await test_transcription_insertion()
    await analyze_webhook_configuration()
    
    print("\n=== Next Steps ===")
    print("1. Make a test call and monitor server logs")
    print("2. Look for webhook callback requests in logs")
    print("3. Check if OpenAI WebSocket events are being received")
    print("4. If no webhook calls are seen, check Twilio webhook configuration")

if __name__ == "__main__":
    asyncio.run(main())
