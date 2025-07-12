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
    """Service for handling call transcriptions with database persistence."""
    
    def __init__(self, prisma_service=None):
        self.active_transcriptions: Dict[str, CallTranscription] = {}
        self.completed_transcriptions: Dict[str, CallTranscription] = {}
        self.prisma_service = prisma_service
        logger.info("TranscriptionService initialized with database persistence")
    
    def set_prisma_service(self, prisma_service):
        """Set the Prisma service for database operations."""
        self.prisma_service = prisma_service
    
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
    
    async def end_call_transcription(self, call_sid: str) -> Optional[CallTranscription]:
        """End transcription for a call, save to database, and move it to completed."""
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
            
            # Save to database if Prisma service is available
            if self.prisma_service:
                await self._save_transcription_to_database(call_sid, transcription)
            
            # Move to completed transcriptions
            self.completed_transcriptions[call_sid] = transcription
            del self.active_transcriptions[call_sid]
            
            logger.info(f"Ended transcription for call {call_sid}")
            self._log_call_summary(transcription)
            
            return transcription
            
        except Exception as e:
            logger.error(f"Error ending transcription for call {call_sid}: {str(e)}")
            raise
    
    async def _save_transcription_to_database(self, call_sid: str, transcription: CallTranscription):
        """Save transcription entries to the database."""
        try:
            if not self.prisma_service:
                logger.warning("No Prisma service available for saving transcriptions")
                return
            
            # Get the call log ID
            call_log = await self.prisma_service.get_call_log(call_sid)
            if not call_log:
                logger.error(f"Call log not found for {call_sid}, cannot save transcriptions")
                return
            
            # Prepare transcriptions for batch insertion
            transcription_data = []
            for entry in transcription.entries:
                if entry.is_final:  # Only save final transcriptions
                    transcription_data.append({
                        'call_log_id': call_log.id,
                        'speaker': entry.speaker.value,
                        'text': entry.text,
                        'confidence': entry.confidence,
                        'is_final': entry.is_final,
                        'timestamp': entry.timestamp
                    })
            
            if transcription_data:
                # Use batch insertion for better performance
                await self.prisma_service.add_transcriptions_batch(transcription_data)
                logger.info(f"Saved {len(transcription_data)} transcription entries to database for call {call_sid}")
            else:
                logger.warning(f"No final transcriptions to save for call {call_sid}")
                
        except Exception as e:
            logger.error(f"Error saving transcriptions to database for call {call_sid}: {str(e)}")
    
    async def _extract_call_context(self, transcriptions, call) -> dict:
        """Extract meaningful context from transcriptions."""
        try:
            context = {
                'business_info': {},
                'pain_points': [],
                'conversation_summary': '',
                'call_date': call.startTime.strftime('%Y-%m-%d %H:%M')
            }
            
            # Process each transcription entry
            for t in transcriptions:
                logger.info(f"Processing transcription entry: {t.text[:50]}... (Speaker: {t.speaker})")
                text = t.text.lower()
                speaker = t.speaker.lower()
                
                # Skip if this is a JSON conversation entry
                if t.speaker == "conversation":
                    try:
                        # Parse JSON conversation data
                        conversation_data = json.loads(t.text)
                        for entry in conversation_data:
                            entry_text = entry.get('text', '').lower()
                            entry_speaker = entry.get('speaker', '').lower()
                            
                            # Extract business information from user responses
                            if entry_speaker == 'user':
                                self._extract_business_info(entry_text, context)
                                self._extract_pain_points(entry_text, context)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON conversation data: {t.text[:100]}...")
                        continue
                else:
                    # Handle individual transcription entries
                    if speaker == 'user':
                        self._extract_business_info(text, context)
                        self._extract_pain_points(text, context)
            
            return context
            
        except Exception as e:
            logger.error(f"Error extracting call context: {str(e)}")
            return {}
    
    def _extract_business_info(self, text: str, context: dict):
        """Extract business information from text."""
        text_lower = text.lower()
        
        # Business type detection
        business_types = {
            'restaurant': ['restaurant', 'cafe', 'café', 'food', 'dining', 'kitchen', 'chef'],
            'retail': ['shop', 'store', 'retail', 'clothing', 'fashion', 'boutique'],
            'service': ['service', 'consulting', 'agency', 'freelance', 'contractor'],
            'technology': ['tech', 'software', 'app', 'digital', 'online', 'web'],
            'healthcare': ['clinic', 'hospital', 'medical', 'health', 'doctor', 'pharmacy'],
            'manufacturing': ['factory', 'manufacturing', 'production', 'industrial'],
            'construction': ['construction', 'building', 'contractor', 'renovation']
        }
        
        for business_type, keywords in business_types.items():
            if any(keyword in text_lower for keyword in keywords):
                context['business_info']['type'] = business_type
                break
        
        # Company name detection (look for capitalized words that might be company names)
        words = text.split()
        potential_names = []
        for word in words:
            if word[0].isupper() and len(word) > 2 and word.lower() not in ['the', 'and', 'for', 'with', 'from', 'this', 'that']:
                potential_names.append(word)
        
        if potential_names:
            context['business_info']['potential_name'] = ' '.join(potential_names[:3])  # Take first 3 words
        
        # Business size indicators
        size_indicators = {
            'small': ['small', 'startup', 'family', 'local', 'independent'],
            'medium': ['medium', 'growing', 'established', 'team'],
            'large': ['large', 'corporate', 'chain', 'franchise', 'multiple locations']
        }
        
        for size, keywords in size_indicators.items():
            if any(keyword in text_lower for keyword in keywords):
                context['business_info']['size'] = size
                break
    
    def _extract_pain_points(self, text: str, context: dict):
        """Extract pain points from text."""
        text_lower = text.lower()
        
        pain_point_keywords = {
            'high_fees': ['expensive', 'high fees', 'costly', 'too much', 'overpriced'],
            'slow_settlements': ['slow', 'delay', 'waiting', 'settlement', 'payment'],
            'poor_support': ['support', 'help', 'service', 'response', 'customer service'],
            'technical_issues': ['problem', 'issue', 'broken', 'not working', 'error'],
            'limited_features': ['limited', 'missing', 'need more', 'want more'],
            'complex_setup': ['complicated', 'difficult', 'hard to', 'complex', 'setup']
        }
        
        for pain_point, keywords in pain_point_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                context['pain_points'].append(pain_point)
    
    def _create_context_summary(self, business_info: dict, pain_points: list, phone_number: str) -> str:
        """Create a comprehensive context summary for the AI agent."""
        summary_parts = []
        
        # Business information summary
        if business_info:
            summary_parts.append("PREVIOUS CALL CONTEXT:")
            
            if 'type' in business_info:
                summary_parts.append(f"- Business type: {business_info['type'].title()}")
            
            if 'potential_name' in business_info:
                summary_parts.append(f"- Potential company name: {business_info['potential_name']}")
            
            if 'size' in business_info:
                summary_parts.append(f"- Business size: {business_info['size']}")
        
        # Pain points summary
        if pain_points:
            summary_parts.append("\nPREVIOUS PAIN POINTS IDENTIFIED:")
            pain_point_descriptions = {
                'high_fees': "High processing fees",
                'slow_settlements': "Slow payment settlements",
                'poor_support': "Poor customer support",
                'technical_issues': "Technical problems with current system",
                'limited_features': "Limited features in current solution",
                'complex_setup': "Complex setup process"
            }
            
            for pain_point in pain_points:
                if pain_point in pain_point_descriptions:
                    summary_parts.append(f"- {pain_point_descriptions[pain_point]}")
        
        # Instructions for the AI
        if business_info or pain_points:
            summary_parts.append("\nINSTRUCTIONS:")
            summary_parts.append("- Acknowledge this is a follow-up call")
            summary_parts.append("- Reference previous conversation naturally")
            summary_parts.append("- Focus on addressing identified pain points")
            summary_parts.append("- Ask about progress since last call")
            summary_parts.append("- Be more specific about how Teya can help based on their business type")
        
        return "\n".join(summary_parts) if summary_parts else ""
    
    async def get_previous_call_context(self, phone_number: str, limit: int = 3) -> str:
        """Get context from previous calls to the same phone number."""
        try:
            if not self.prisma_service:
                logger.warning("No Prisma service available for retrieving call context")
                return ""
            
            # Get previous calls to this phone number
            previous_calls = await self.prisma_service.get_calls_by_phone_number(phone_number, limit)
            
            if not previous_calls:
                logger.info(f"No previous calls found for {phone_number}")
                return ""
            
            context_parts = []
            business_info = {}
            pain_points = []
            
            for call in previous_calls:
                if call.id:
                    logger.info(f"Processing previous call {call.id} for {phone_number}")
                    # Get transcriptions for this call
                    if self.prisma_service:
                        logger.info(f"Retrieving transcriptions for call {call.id}")
                    else:
                        logger.warning("No Prisma service available to retrieve transcriptions")
                        
                    transcriptions = await self.prisma_service.get_transcriptions_for_call(call.id)
                    logger.info(f"Found {len(transcriptions)} transcriptions for call {call.id}")
                    if transcriptions:
                        # Parse conversation data and extract context
                        call_context = await self._extract_call_context(transcriptions, call)
                        if call_context:
                            context_parts.append(call_context)
                            
                            # Extract business information and pain points
                            business_info.update(call_context.get('business_info', {}))
                            pain_points.extend(call_context.get('pain_points', []))
            
            if context_parts:
                context_summary = self._create_context_summary(business_info, pain_points, phone_number)
                logger.info(f"Retrieved context from {len(previous_calls)} previous calls for {phone_number}")
                return context_summary
            
            return ""
            
        except Exception as e:
            logger.error(f"Error getting previous call context for {phone_number}: {str(e)}")
            return ""
    
    async def get_call_confidence_score(self, call_sid: str) -> Dict[str, Any]:
        """Calculate confidence scores for a call's transcriptions."""
        try:
            if not self.prisma_service:
                return {"error": "No Prisma service available"}
            
            call_log = await self.prisma_service.get_call_log(call_sid)
            if not call_log:
                return {"error": "Call not found"}
            
            transcriptions = await self.prisma_service.get_transcriptions_for_call(call_log.id)
            
            if not transcriptions:
                return {"error": "No transcriptions found"}
            
            # Calculate confidence statistics
            confidence_values = [t.confidence for t in transcriptions if t.confidence is not None]
            
            if not confidence_values:
                return {
                    "average_confidence": None,
                    "min_confidence": None,
                    "max_confidence": None,
                    "confidence_count": 0,
                    "total_transcriptions": len(transcriptions)
                }
            
            avg_confidence = sum(confidence_values) / len(confidence_values)
            min_confidence = min(confidence_values)
            max_confidence = max(confidence_values)
            
            # Calculate confidence by speaker
            user_confidences = [t.confidence for t in transcriptions if t.speaker == "user" and t.confidence is not None]
            assistant_confidences = [t.confidence for t in transcriptions if t.speaker == "assistant" and t.confidence is not None]
            
            result = {
                "average_confidence": round(avg_confidence, 3),
                "min_confidence": round(min_confidence, 3),
                "max_confidence": round(max_confidence, 3),
                "confidence_count": len(confidence_values),
                "total_transcriptions": len(transcriptions),
                "user_average_confidence": round(sum(user_confidences) / len(user_confidences), 3) if user_confidences else None,
                "assistant_average_confidence": round(sum(assistant_confidences) / len(assistant_confidences), 3) if assistant_confidences else None
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating confidence score for call {call_sid}: {str(e)}")
            return {"error": str(e)}
    
    def get_call_transcription(self, call_sid: str) -> Optional[CallTranscription]:
        """Get transcription for a specific call from memory."""
        # Check active transcriptions first
        if call_sid in self.active_transcriptions:
            return self.active_transcriptions[call_sid]
        
        # Check completed transcriptions
        if call_sid in self.completed_transcriptions:
            return self.completed_transcriptions[call_sid]
        
        return None
    
    async def get_call_transcription_from_db(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Get transcription for a specific call from database."""
        try:
            if not self.prisma_service:
                return None
            
            call_log = await self.prisma_service.get_call_log(call_sid)
            if not call_log:
                return None
            
            transcriptions = await self.prisma_service.get_transcriptions_for_call(call_log.id)
            
            if not transcriptions:
                return None
            
            # Convert to CallTranscription format
            entries = []
            for t in transcriptions:
                speaker = SpeakerType.USER if t.speaker == "user" else SpeakerType.ASSISTANT
                entry = TranscriptionEntry(
                    call_sid=call_sid,
                    speaker=speaker,
                    text=t.text,
                    timestamp=t.timestamp,
                    confidence=t.confidence,
                    is_final=t.isFinal
                )
                entries.append(entry)
            
            transcription = CallTranscription(
                call_sid=call_sid,
                start_time=call_log.startTime,
                end_time=call_log.endTime,
                entries=entries,
                total_duration=call_log.duration
            )
            
            return transcription.to_dict()
            
        except Exception as e:
            logger.error(f"Error getting transcription from database for call {call_sid}: {str(e)}")
            return None
    
    def get_all_transcriptions(self) -> Dict[str, CallTranscription]:
        """Get all transcriptions (active and completed) from memory."""
        all_transcriptions = {}
        all_transcriptions.update(self.active_transcriptions)
        all_transcriptions.update(self.completed_transcriptions)
        return all_transcriptions
    
    def process_openai_message(self, call_sid: str, message: Dict[str, Any]) -> None:
        """Process OpenAI WebSocket message and extract transcription data."""
        try:
            message_type = message.get("type")
            logger.debug(f"Processing message type '{message_type}' for call {call_sid}")
            
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
            else:
                logger.debug(f"Unhandled message type '{message_type}' for call {call_sid}")
                
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
            confidence = message.get("confidence")
            if transcript:
                self.add_transcription_entry(
                    call_sid, 
                    SpeakerType.ASSISTANT, 
                    transcript, 
                    confidence=confidence,
                    is_final=True
                )
                
        except Exception as e:
            logger.error(f"Error handling audio transcript done: {str(e)}")
    
    def _handle_input_transcription_completed(self, call_sid: str, message: Dict[str, Any]) -> None:
        """Handle completed input audio transcription."""
        try:
            transcript = message.get("transcript", "")
            confidence = message.get("confidence")
            if transcript:
                self.add_transcription_entry(
                    call_sid, 
                    SpeakerType.USER, 
                    transcript, 
                    confidence=confidence,
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