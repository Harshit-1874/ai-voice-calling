#!/usr/bin/env python3
"""
Comprehensive test script to test transcription functionality
"""

import asyncio
import requests
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

async def test_full_transcription_flow():
    """Test the complete transcription flow"""
    
    print("=== Comprehensive Transcription Test ===")
    print()
    
    # Test 1: Check server health
    print("1. Testing server connectivity...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Server is running")
        else:
            print(f"✗ Server returned status: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Server not reachable: {e}")
        return
    
    # Test 2: Check current transcription count
    print("2. Checking current transcription count...")
    try:
        response = requests.get(f"{BASE_URL}/transcriptions/recent", timeout=5)
        if response.status_code == 200:
            data = response.json()
            initial_count = data.get("total_transcriptions", 0)
            print(f"✓ Current transcriptions in database: {initial_count}")
        else:
            print(f"✗ Failed to get transcriptions: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Error getting transcriptions: {e}")
        return
    
    # Test 3: Test webhook endpoints
    print("3. Testing webhook endpoints...")
    webhook_endpoints = [
        "/recording-callback",
        "/transcription-callback"
    ]
    
    for endpoint in webhook_endpoints:
        try:
            # Test with OPTIONS to see if endpoint exists
            response = requests.options(f"{BASE_URL}{endpoint}", timeout=5)
            print(f"✓ Endpoint {endpoint} exists (status: {response.status_code})")
        except Exception as e:
            print(f"✗ Endpoint {endpoint} error: {e}")
    
    # Test 4: Simulate a call initiation to see TwiML generation
    print("4. Testing TwiML generation...")
    try:
        test_phone = "+1234567890"  # Test phone number
        response = requests.post(
            f"{BASE_URL}/make-call",
            json={"phone_number": test_phone},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            call_sid = data.get("call_sid")
            print(f"✓ Test call initiated successfully")
            print(f"  Call SID: {call_sid}")
            
            # Wait a bit then check if call log was created
            time.sleep(2)
            
            # Check call logs
            response = requests.get(f"{BASE_URL}/call-logs", timeout=5)
            if response.status_code == 200:
                call_logs = response.json().get("call_logs", [])
                recent_call = next((call for call in call_logs if call["call_sid"] == call_sid), None)
                if recent_call:
                    print(f"✓ Call log created: {recent_call['status']}")
                else:
                    print("✗ Call log not found")
            
        else:
            print(f"✗ Call initiation failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"✗ Call test error: {e}")
    
    # Test 5: Instructions for manual testing
    print()
    print("=== Manual Testing Instructions ===")
    print("To test transcription functionality:")
    print("1. Make a real call to your Twilio number")
    print("2. Monitor the server logs for:")
    print("   - 'POST /recording-callback' requests from Twilio")
    print("   - 'POST /transcription-callback' requests from Twilio")
    print("   - 'Received OpenAI event:' messages during WebSocket calls")
    print("   - 'TRANSCRIPTION STORED:' messages")
    print()
    print("3. After the call, check transcriptions again:")
    print(f"   curl {BASE_URL}/transcriptions/recent")
    print()
    print("4. If no transcriptions appear, check:")
    print("   - Twilio webhook URLs in console")
    print("   - OpenAI session configuration")
    print("   - Network connectivity for webhooks")

if __name__ == "__main__":
    asyncio.run(test_full_transcription_flow())
