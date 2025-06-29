#!/usr/bin/env python3
"""
Debug script to monitor OpenAI WebSocket events and understand what's happening during a call
"""

import asyncio
import json
import logging
from services.websocket_service import WebSocketService

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_openai_events():
    """Debug OpenAI WebSocket events"""
    
    print("=== OpenAI WebSocket Event Debug ===")
    print("This will help us understand what events are being received during calls")
    print()
    
    # Check the current session configuration
    websocket_service = WebSocketService()
    
    print("Current LOG_EVENT_TYPES:")
    from services.websocket_service import LOG_EVENT_TYPES
    for event_type in LOG_EVENT_TYPES:
        print(f"  - {event_type}")
    
    print()
    print("Current SYSTEM_MESSAGE (first 200 chars):")
    from services.websocket_service import SYSTEM_MESSAGE
    print(f"  {SYSTEM_MESSAGE[:200]}...")
    
    print()
    print("=== Recommendations for debugging ===")
    print("1. Make a test call and watch the logs for 'Received OpenAI event:' messages")
    print("2. Look for events like:")
    print("   - session.created")
    print("   - conversation.item.created")  
    print("   - conversation.item.input_audio_transcription.completed")
    print("   - response.content.done")
    print("   - response.done")
    print()
    print("3. If you don't see transcription events, the issue might be:")
    print("   - OpenAI session configuration")
    print("   - Audio format incompatibility") 
    print("   - Transcription not enabled properly")
    print()
    
    # Check current transcription count
    from services.prisma_service import PrismaService
    prisma_service = PrismaService()
    
    try:
        async with prisma_service:
            total_transcriptions = await prisma_service.prisma.transcription.count()
            openai_transcriptions = await prisma_service.prisma.transcription.count(
                where={"sessionId": {"contains": "chatcmpl"}}  # OpenAI session IDs typically start with chatcmpl
            )
            
            print(f"Current transcription stats:")
            print(f"  - Total transcriptions in DB: {total_transcriptions}")
            print(f"  - OpenAI transcriptions: {openai_transcriptions}")
            print(f"  - Twilio transcriptions: {total_transcriptions - openai_transcriptions}")
            
    except Exception as e:
        print(f"Error checking transcription stats: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_openai_events())
