#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.prisma_service import PrismaService

async def check_recent_calls():
    """Check recent call logs"""
    prisma = PrismaService()
    
    try:
        await prisma.connect()
        
        # Get recent calls
        calls = await prisma.prisma.calllog.find_many(
            take=10,
            order={'startTime': 'desc'},
            include={
                'transcriptions': True
            }
        )
        
        print(f"Found {len(calls)} recent calls:")
        print("-" * 80)
        
        for call in calls:
            print(f"Call SID: {call.callSid}")
            print(f"  Status: {call.status}")
            print(f"  Duration: {call.duration}")
            print(f"  Created: {call.startTime}")
            print(f"  Updated: {call.endTime}")
            
            if call.transcriptions:
                print(f"  Transcriptions: {len(call.transcriptions)}")
                for trans in call.transcriptions:
                    print(f"    - {trans.speaker}: {trans.text[:100]}...")
            else:
                print(f"  Transcriptions: None")
            print()
            
        # Also check if we have any transcriptions at all
        all_transcriptions = await prisma.prisma.transcription.find_many(
            take=5,
            order={'timestamp': 'desc'}
        )
        
        print(f"\nTotal transcriptions in database: {len(all_transcriptions)}")
        if all_transcriptions:
            print("Recent transcriptions:")
            for trans in all_transcriptions:
                print(f"  - Call Log ID: {trans.callLogId}, Speaker: {trans.speaker}, Length: {len(trans.text)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await prisma.disconnect()

if __name__ == "__main__":
    asyncio.run(check_recent_calls())
