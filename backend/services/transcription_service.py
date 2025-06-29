#!/usr/bin/env python3
"""
Enhanced transcription service inspired by the Deepgram implementation
Handles both Twilio recording callbacks and OpenAI real-time transcription
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import base64
from services.prisma_service import PrismaService

logger = logging.getLogger(__name__)

class TranscriptionService:
    """
    Enhanced transcription service that handles multiple sources:
    1. OpenAI real-time transcription via WebSocket
    2. Twilio recording transcription via webhooks
    """
    
    def __init__(self):
        self.prisma_service = PrismaService()
        self.active_sessions = {}  # Track active call sessions
        self.partial_transcripts = {}  # Buffer for partial transcripts
        self.final_results = {}  # Store final results per session
        self.speech_final_flags = {}  # Track speech final states
        
    async def initialize_session(self, call_sid: str, session_id: str = None):
        """Initialize a transcription session for a call"""
        try:
            session_data = {
                'call_sid': call_sid,
                'session_id': session_id,
                'start_time': datetime.now(),
                'partial_transcript': '',
                'final_result': '',
                'speech_final': False,
                'total_transcripts': 0,
                'last_activity': datetime.now()
            }
            
            self.active_sessions[call_sid] = session_data
            self.partial_transcripts[call_sid] = ''
            self.final_results[call_sid] = ''
            self.speech_final_flags[call_sid] = False
            
            logger.info(f"Initialized transcription session for call {call_sid}")
            return session_data
            
        except Exception as e:
            logger.error(f"Error initializing transcription session: {str(e)}")
            return None
    
    async def process_openai_transcript(self, call_sid: str, speaker: str, text: str, 
                                     is_final: bool = False, is_speech_final: bool = False,
                                     confidence: float = None, session_id: str = None):
        """
        Process OpenAI transcription events with proper buffering and finalization
        Similar to the Deepgram approach with is_final and speech_final logic
        """
        try:
            if call_sid not in self.active_sessions:
                await self.initialize_session(call_sid, session_id)
            
            session = self.active_sessions[call_sid]
            session['last_activity'] = datetime.now()
            
            # Handle text processing similar to Deepgram logic
            if text and text.strip():
                # If this is a final chunk, add it to the final result
                if is_final and text.strip():
                    if call_sid not in self.final_results:
                        self.final_results[call_sid] = ''
                    
                    self.final_results[call_sid] += f" {text.strip()}"
                    
                    # If speech is final (natural pause detected), save to database
                    if is_speech_final:
                        self.speech_final_flags[call_sid] = True
                        final_text = self.final_results[call_sid].strip()
                        
                        if final_text:
                            await self.store_transcription(
                                call_sid=call_sid,
                                speaker=speaker,
                                text=final_text,
                                confidence=confidence,
                                session_id=session_id,
                                is_final=True
                            )
                            
                            # Reset for next utterance
                            self.final_results[call_sid] = ''
                            session['total_transcripts'] += 1
                            
                            logger.info(f"Stored final transcript for {call_sid}: {speaker} - {final_text[:50]}...")
                    else:
                        # Reset speech final flag for subsequent processing
                        self.speech_final_flags[call_sid] = False
                else:
                    # Handle partial/interim results
                    self.partial_transcripts[call_sid] = text
                    logger.debug(f"Partial transcript for {call_sid}: {speaker} - {text[:30]}...")
            
        except Exception as e:
            logger.error(f"Error processing OpenAI transcript: {str(e)}")
    
    async def handle_utterance_end(self, call_sid: str, speaker: str = "customer", session_id: str = None):
        """
        Handle utterance end events - save accumulated text if speech_final hasn't occurred
        Similar to the Deepgram UtteranceEnd handling
        """
        try:
            if call_sid in self.speech_final_flags and not self.speech_final_flags[call_sid]:
                # Speech final hasn't occurred, so emit the accumulated text
                final_text = self.final_results.get(call_sid, '').strip()
                
                if final_text:
                    logger.info(f"UtteranceEnd received before speechFinal, saving accumulated text: {final_text}")
                    
                    await self.store_transcription(
                        call_sid=call_sid,
                        speaker=speaker,
                        text=final_text,
                        confidence=0.9,  # Default confidence for utterance end
                        session_id=session_id,
                        is_final=True
                    )
                    
                    # Reset for next utterance
                    self.final_results[call_sid] = ''
                    if call_sid in self.active_sessions:
                        self.active_sessions[call_sid]['total_transcripts'] += 1
                else:
                    logger.debug("UtteranceEnd received but no accumulated text to save")
            else:
                logger.debug("Speech was already final when UtteranceEnd received")
                
        except Exception as e:
            logger.error(f"Error handling utterance end: {str(e)}")
    
    async def store_transcription(self, call_sid: str, speaker: str, text: str, 
                                confidence: float = None, session_id: str = None, 
                                is_final: bool = True, source: str = "openai"):
        """Enhanced transcription storage with better error handling and logging"""
        try:
            if not text or not text.strip():
                logger.debug("Skipping empty transcription")
                return False
                
            async with self.prisma_service:
                # Get call log
                call_log = await self.prisma_service.get_call_log(call_sid)
                if not call_log:
                    logger.warning(f"Call log not found for call_sid: {call_sid}")
                    return False
                
                # Store transcription
                transcription = await self.prisma_service.add_transcription(
                    call_log_id=call_log.id,
                    speaker=speaker,
                    text=text.strip(),
                    confidence=confidence,
                    session_id=session_id,
                    is_final=is_final
                )
                
                logger.info(f"✅ Stored {source} transcription for {call_sid}: {speaker} - {text[:100]}...")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error storing transcription: {str(e)}")
            return False
    
    async def process_twilio_transcription(self, call_sid: str, transcription_text: str, 
                                        confidence: float = None, recording_url: str = None):
        """Process Twilio recording transcription callback"""
        try:
            logger.info(f"Processing Twilio transcription for call {call_sid}")
            
            if not transcription_text or not transcription_text.strip():
                logger.warning("Received empty Twilio transcription")
                return False
            
            # Store the full Twilio transcription as a single entry
            success = await self.store_transcription(
                call_sid=call_sid,
                speaker="conversation",  # Twilio transcribes the entire conversation
                text=transcription_text.strip(),
                confidence=confidence,
                session_id=None,
                is_final=True,
                source="twilio"
            )
            
            # Update call log with recording URL if provided
            if recording_url and success:
                async with self.prisma_service:
                    await self.prisma_service.update_call_status(
                        call_sid=call_sid,
                        status="completed",  # Keep existing status or set appropriate one
                        recording_url=recording_url
                    )
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing Twilio transcription: {str(e)}")
            return False
    
    async def finalize_session(self, call_sid: str):
        """Clean up session when call ends"""
        try:
            if call_sid in self.active_sessions:
                session = self.active_sessions[call_sid]
                
                # Save any remaining partial transcript
                final_text = self.final_results.get(call_sid, '').strip()
                if final_text:
                    await self.store_transcription(
                        call_sid=call_sid,
                        speaker="customer",
                        text=final_text,
                        confidence=0.8,
                        session_id=session.get('session_id'),
                        is_final=True,
                        source="openai_final"
                    )
                
                # Log session stats
                logger.info(f"Finalized transcription session for {call_sid}: "
                          f"{session['total_transcripts']} transcripts stored")
                
                # Clean up
                del self.active_sessions[call_sid]
                self.partial_transcripts.pop(call_sid, None)
                self.final_results.pop(call_sid, None)
                self.speech_final_flags.pop(call_sid, None)
            
        except Exception as e:
            logger.error(f"Error finalizing transcription session: {str(e)}")
    
    def get_session_stats(self, call_sid: str) -> Dict[str, Any]:
        """Get transcription statistics for a session"""
        if call_sid not in self.active_sessions:
            return {"error": "Session not found"}
        
        session = self.active_sessions[call_sid]
        return {
            "call_sid": call_sid,
            "session_id": session.get('session_id'),
            "start_time": session['start_time'].isoformat(),
            "last_activity": session['last_activity'].isoformat(),
            "total_transcripts": session['total_transcripts'],
            "current_partial": self.partial_transcripts.get(call_sid, ''),
            "current_final": self.final_results.get(call_sid, ''),
            "speech_final": self.speech_final_flags.get(call_sid, False)
        }
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old inactive sessions"""
        try:
            current_time = datetime.now()
            to_remove = []
            
            for call_sid, session in self.active_sessions.items():
                age_hours = (current_time - session['last_activity']).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(call_sid)
            
            for call_sid in to_remove:
                await self.finalize_session(call_sid)
                logger.info(f"Cleaned up old transcription session: {call_sid}")
            
            return len(to_remove)
            
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {str(e)}")
            return 0
