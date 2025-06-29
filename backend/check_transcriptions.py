#!/usr/bin/env python3
"""
Check transcriptions in the database
"""

import asyncio
from services.prisma_service import PrismaService

async def check_transcriptions():
    """Check if any transcriptions exist in the database"""
    
    prisma_service = PrismaService()
    
    try:
        async with prisma_service:
            # Get all transcriptions
            transcriptions = await prisma_service.prisma.transcription.find_many(
                order={"timestamp": "desc"},
                take=10,
                include={
                    "callLog": True
                }
            )
            
            print(f"Found {len(transcriptions)} transcriptions in database:")
            
            for t in transcriptions:
                print(f"  ID: {t.id}")
                print(f"  Speaker: {t.speaker}")
                print(f"  Text: {t.text}")
                print(f"  Confidence: {t.confidence}")
                print(f"  Timestamp: {t.timestamp}")
                print(f"  Call SID: {t.callLog.callSid if t.callLog else 'Unknown'}")
                print(f"  Is Final: {t.isFinal}")
                print(f"  Session ID: {t.sessionId}")
                print("-" * 50)
            
            if len(transcriptions) == 0:
                print("No transcriptions found in database.")
                print("This suggests that OpenAI transcription events are not being captured.")
            
    except Exception as e:
        print(f"Error checking transcriptions: {str(e)}")

if __name__ == "__main__":
    asyncio.run(check_transcriptions())
