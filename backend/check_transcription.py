#!/usr/bin/env python3
"""
Script to check transcription status for a specific call.
"""

import asyncio
import logging
from services.transcription_service import TranscriptionService, SpeakerType
from services.prisma_service import PrismaService
from services.websocket_service import WebSocketService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_transcription_status(call_sid: str):
    """Check transcription status for a specific call."""
    try:
        # Initialize services
        prisma_service = PrismaService()
        websocket_service = WebSocketService()
        
        logger.info(f"Checking transcription status for call: {call_sid}")
        
        # Check transcription service
        transcription_service = websocket_service.get_transcription_service()
        memory_transcription = transcription_service.get_call_transcription(call_sid)
        
        logger.info(f"Memory transcription: {memory_transcription is not None}")
        if memory_transcription:
            logger.info(f"Memory entries: {len(memory_transcription.entries)}")
            for i, entry in enumerate(memory_transcription.entries):
                logger.info(f"  Entry {i+1}: {entry.speaker.value} - {entry.text[:50]}...")
        
        # Check buffer
        buffer_transcriptions = 0
        if call_sid in websocket_service.transcription_buffers:
            buffer = websocket_service.transcription_buffers[call_sid]
            buffer_transcriptions = buffer.get_transcription_count()
            logger.info(f"Buffer transcriptions: {buffer_transcriptions}")
            for i, t in enumerate(buffer.transcriptions):
                logger.info(f"  Buffer entry {i+1}: {t['speaker']} - {t['text'][:50]}...")
        
        # Check database
        async with prisma_service:
            call_log = await prisma_service.get_call_log(call_sid)
            if call_log:
                logger.info(f"Call log found with ID: {call_log.id}")
                db_transcriptions = await prisma_service.get_transcriptions_for_call(call_log.id)
                logger.info(f"Database transcriptions: {len(db_transcriptions)}")
                for i, t in enumerate(db_transcriptions):
                    logger.info(f"  DB entry {i+1}: {t.speaker} - {t.text[:50]}...")
            else:
                logger.warning("Call log not found")
        
        # Summary
        logger.info("="*50)
        logger.info("TRANSCRIPTION STATUS SUMMARY")
        logger.info(f"Call SID: {call_sid}")
        logger.info(f"In memory: {memory_transcription is not None}")
        logger.info(f"In buffer: {buffer_transcriptions > 0}")
        logger.info(f"In database: {len(db_transcriptions) if 'db_transcriptions' in locals() else 0}")
        logger.info(f"Active transcriptions: {list(transcription_service.active_transcriptions.keys())}")
        logger.info(f"Completed transcriptions: {list(transcription_service.completed_transcriptions.keys())}")
        logger.info(f"Buffer keys: {list(websocket_service.transcription_buffers.keys())}")
        
    except Exception as e:
        logger.error(f"Error checking transcription status: {str(e)}")
        raise

async def main():
    """Main function."""
    call_sid = "CAd4f718569fe1a84228b1a7a81acbc3de"  # Your call SID
    await check_transcription_status(call_sid)

if __name__ == "__main__":
    asyncio.run(main()) 