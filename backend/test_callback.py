#!/usr/bin/env python3
"""
Script to simulate a Twilio transcription callback for testing
"""

import asyncio
import requests
import json
from urllib.parse import urlencode

async def test_transcription_callback():
    """Test transcription callback by simulating Twilio's POST request"""
    
    # Your ngrok URL from the .env file
    base_url = "https://c97f-101-0-63-56.ngrok-free.app"
    callback_url = f"{base_url}/transcription-callback"
    
    # Sample data that Twilio would send in a transcription callback
    callback_data = {
        "CallSid": "TEST_CALL_SID_12345",
        "RecordingSid": "RE123456789abcdef",
        "TranscriptionSid": "TR123456789abcdef", 
        "TranscriptionText": "Hello, I'm calling from Teya UK about payment solutions. I'd like to learn more about your business and see how we can help with your payment processing needs. Could you tell me a bit about your current setup?",
        "TranscriptionStatus": "completed",
        "Confidence": "0.89",
        "AccountSid": "AC123456789abcdef",
        "TranscriptionUrl": "https://api.twilio.com/2010-04-01/Accounts/AC123/Transcriptions/TR123"
    }
    
    print("Simulating Twilio transcription callback...")
    print(f"Callback URL: {callback_url}")
    print(f"Callback data: {json.dumps(callback_data, indent=2)}")
    
    try:
        # Send POST request simulating Twilio's callback
        response = requests.post(
            callback_url,
            data=callback_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "TwilioProxy/1.1"
            },
            timeout=10
        )
        
        print(f"\nResponse status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Transcription callback test successful!")
        else:
            print(f"\n❌ Transcription callback test failed with status {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error sending callback request: {str(e)}")
        print("Make sure your backend server is running and accessible via ngrok")

if __name__ == "__main__":
    asyncio.run(test_transcription_callback())
