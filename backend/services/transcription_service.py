import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class SpeakerType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

@dataclass
class TranscriptionEntry:
    """Data class for individual transcription entries."""
    call_sid: str
    speaker: SpeakerType
    text: str
    timestamp: datetime
    confidence: Optional[float] = None
    audio_duration: Optional[float] = None
    is_final: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['speaker'] = self.speaker.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class CallTranscription:
    """Data class for complete call transcription."""
    call_sid: str
    start_time: datetime
    end_time: Optional[datetime] = None
    entries: List[TranscriptionEntry] = None
    total_duration: Optional[float] = None
    
    def __post_init__(self):
        if self.entries is None:
            self.entries = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'call_sid': self.call_sid,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_duration': self.total_duration,
            'entries': [entry.to_dict() for entry in self.entries],
            'entry_count': len(self.entries)
        }

class TranscriptionService:
    """Service for handling call transcriptions."""
    
    def __init__(self):
        self.active_transcriptions: Dict[str, CallTranscription] = {}
        self.completed_transcriptions: Dict[str, CallTranscription] = {}
        logger.info("TranscriptionService initialized")
    
    def start_call_transcription(self, call_sid: str) -> CallTranscription:
        """Start transcription for a new call."""
        try:
            if call_sid in self.active_transcriptions:
                logger.warning(f"Transcription already active for call {call_sid}")
                return self.active_transcriptions[call_sid]
            
            transcription = CallTranscription(
                call_sid=call_sid,
                start_time=datetime.now()
            )
            
            self.active_transcriptions[call_sid] = transcription
            logger.info(f"Started transcription for call {call_sid}")
            
            return transcription
            
        except Exception as e:
            logger.error(f"Error starting transcription for call {call_sid}: {str(e)}")
            raise
    
    def add_transcription_entry(
        self, 
        call_sid: str, 
        speaker: SpeakerType, 
        text: str, 
        confidence: Optional[float] = None,
        audio_duration: Optional[float] = None,
        is_final: bool = True
    ) -> None:
        """Add a transcription entry to an active call."""
        try:
            if call_sid not in self.active_transcriptions:
                logger.warning(f"No active transcription found for call {call_sid}, starting new one")
                self.start_call_transcription(call_sid)
            
            entry = TranscriptionEntry(
                call_sid=call_sid,
                speaker=speaker,
                text=text,
                timestamp=datetime.now(),
                confidence=confidence,
                audio_duration=audio_duration,
                is_final=is_final
            )
            
            self.active_transcriptions[call_sid].entries.append(entry)
            
            # Log the transcription entry
            self._log_transcription_entry(entry)
            
        except Exception as e:
            logger.error(f"Error adding transcription entry for call {call_sid}: {str(e)}")
            raise
    
    def end_call_transcription(self, call_sid: str) -> Optional[CallTranscription]:
        """End transcription for a call and move it to completed."""
        try:
            if call_sid not in self.active_transcriptions:
                logger.warning(f"No active transcription found for call {call_sid}")
                return None
            
            transcription = self.active_transcriptions[call_sid]
            transcription.end_time = datetime.now()
            
            if transcription.start_time and transcription.end_time:
                transcription.total_duration = (
                    transcription.end_time - transcription.start_time
                ).total_seconds()
            
            # Move to completed transcriptions
            self.completed_transcriptions[call_sid] = transcription
            del self.active_transcriptions[call_sid]
            
            logger.info(f"Ended transcription for call {call_sid}")
            self._log_call_summary(transcription)
            
            return transcription
            
        except Exception as e:
            logger.error(f"Error ending transcription for call {call_sid}: {str(e)}")
            raise
    
    def get_call_transcription(self, call_sid: str) -> Optional[CallTranscription]:
        """Get transcription for a specific call."""
        # Check active transcriptions first
        if call_sid in self.active_transcriptions:
            return self.active_transcriptions[call_sid]
        
        # Check completed transcriptions
        if call_sid in self.completed_transcriptions:
            return self.completed_transcriptions[call_sid]
        
        return None
    
    def get_all_transcriptions(self) -> Dict[str, CallTranscription]:
        """Get all transcriptions (active and completed)."""
        all_transcriptions = {}
        all_transcriptions.update(self.active_transcriptions)
        all_transcriptions.update(self.completed_transcriptions)
        return all_transcriptions
    
    def process_openai_message(self, call_sid: str, message: Dict[str, Any]) -> None:
        """Process OpenAI WebSocket message and extract transcription data."""
        try:
            message_type = message.get("type")
            
            if message_type == "conversation.item.created":
                self._handle_conversation_item_created(call_sid, message)
            elif message_type == "response.audio_transcript.delta":
                self._handle_audio_transcript_delta(call_sid, message)
            elif message_type == "response.audio_transcript.done":
                self._handle_audio_transcript_done(call_sid, message)
            elif message_type == "conversation.item.input_audio_transcription.completed":
                self._handle_input_transcription_completed(call_sid, message)
            elif message_type == "conversation.item.input_audio_transcription.failed":
                self._handle_input_transcription_failed(call_sid, message)
                
        except Exception as e:
            logger.error(f"Error processing OpenAI message for call {call_sid}: {str(e)}")
    
    def _handle_conversation_item_created(self, call_sid: str, message: Dict[str, Any]) -> None:
        """Handle conversation item created events."""
        try:
            item = message.get("item", {})
            item_type = item.get("type")
            role = item.get("role")
            
            if item_type == "message" and role:
                content = item.get("content", [])
                for content_part in content:
                    if content_part.get("type") == "text":
                        text = content_part.get("text", "")
                        if text:
                            speaker = SpeakerType.USER if role == "user" else SpeakerType.ASSISTANT
                            self.add_transcription_entry(call_sid, speaker, text)
                            
        except Exception as e:
            logger.error(f"Error handling conversation item created: {str(e)}")
    
    def _handle_audio_transcript_delta(self, call_sid: str, message: Dict[str, Any]) -> None:
        """Handle partial audio transcription updates."""
        try:
            delta = message.get("delta", "")
            if delta:
                # This is a partial transcription, mark as not final
                self.add_transcription_entry(
                    call_sid, 
                    SpeakerType.ASSISTANT, 
                    delta, 
                    is_final=False
                )
                
        except Exception as e:
            logger.error(f"Error handling audio transcript delta: {str(e)}")
    
    def _handle_audio_transcript_done(self, call_sid: str, message: Dict[str, Any]) -> None:
        """Handle completed audio transcription."""
        try:
            transcript = message.get("transcript", "")
            if transcript:
                self.add_transcription_entry(
                    call_sid, 
                    SpeakerType.ASSISTANT, 
                    transcript, 
                    is_final=True
                )
                
        except Exception as e:
            logger.error(f"Error handling audio transcript done: {str(e)}")
    
    def _handle_input_transcription_completed(self, call_sid: str, message: Dict[str, Any]) -> None:
        """Handle completed input audio transcription."""
        try:
            transcript = message.get("transcript", "")
            if transcript:
                self.add_transcription_entry(
                    call_sid, 
                    SpeakerType.USER, 
                    transcript, 
                    is_final=True
                )
                
        except Exception as e:
            logger.error(f"Error handling input transcription completed: {str(e)}")
    
    def _handle_input_transcription_failed(self, call_sid: str, message: Dict[str, Any]) -> None:
        """Handle failed input audio transcription."""
        try:
            error = message.get("error", {})
            error_message = error.get("message", "Transcription failed")
            logger.warning(f"Input transcription failed for call {call_sid}: {error_message}")
            
        except Exception as e:
            logger.error(f"Error handling input transcription failed: {str(e)}")
    
    def _log_transcription_entry(self, entry: TranscriptionEntry) -> None:
        """Log individual transcription entry."""
        status = "FINAL" if entry.is_final else "PARTIAL"
        confidence_str = f" (confidence: {entry.confidence:.2f})" if entry.confidence else ""
        
        logger.info(
            f"TRANSCRIPTION [{entry.call_sid}] [{status}] "
            f"{entry.speaker.value.upper()}: {entry.text}{confidence_str}"
        )
    
    def _log_call_summary(self, transcription: CallTranscription) -> None:
        """Log call transcription summary."""
        logger.info("="*80)
        logger.info(f"CALL TRANSCRIPTION SUMMARY - {transcription.call_sid}")
        logger.info(f"Duration: {transcription.total_duration:.2f} seconds")
        logger.info(f"Total entries: {len(transcription.entries)}")
        logger.info(f"Start time: {transcription.start_time}")
        logger.info(f"End time: {transcription.end_time}")
        
        # Count entries by speaker
        user_count = sum(1 for e in transcription.entries if e.speaker == SpeakerType.USER)
        assistant_count = sum(1 for e in transcription.entries if e.speaker == SpeakerType.ASSISTANT)
        
        logger.info(f"User messages: {user_count}")
        logger.info(f"Assistant messages: {assistant_count}")
        logger.info("="*80)
    
    def export_transcription_json(self, call_sid: str) -> Optional[str]:
        """Export transcription as JSON string."""
        try:
            transcription = self.get_call_transcription(call_sid)
            if not transcription:
                return None
            
            return json.dumps(transcription.to_dict(), indent=2)
            
        except Exception as e:
            logger.error(f"Error exporting transcription JSON for call {call_sid}: {str(e)}")
            return None
    
    def get_transcription_text(self, call_sid: str, include_timestamps: bool = False) -> Optional[str]:
        """Get transcription as formatted text."""
        try:
            transcription = self.get_call_transcription(call_sid)
            if not transcription:
                return None
            
            lines = []
            for entry in transcription.entries:
                if not entry.is_final:
                    continue  # Skip partial transcriptions
                
                speaker_label = entry.speaker.value.upper()
                timestamp_str = f"[{entry.timestamp.strftime('%H:%M:%S')}] " if include_timestamps else ""
                lines.append(f"{timestamp_str}{speaker_label}: {entry.text}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error getting transcription text for call {call_sid}: {str(e)}")
            return None