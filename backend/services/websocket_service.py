import json
import base64
import asyncio
import websockets
import logging
from config import OPENAI_API_KEY
from services.prisma_service import PrismaService
from services.hubspot_service import HubspotService
from services.transcription_service import TranscriptionService, SpeakerType
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# OpenAI Configuration
VOICE = 'echo'

SYSTEM_MESSAGE = (
    "You are a professional sales representative for Teya UK, a leading provider of smart payment solutions for modern businesses. "
    "Your voice should sound like a friendly, professional British woman. "
    "Your goal is to have a natural, flowing conversation to understand the business owner's needs and introduce them to Teya's services.\n\n"
    "CONVERSATION STYLE:\n"
    "- Speak like a real person having a casual business conversation, not a robot.\n"
    "- Use a warm, friendly, and engaging tone.\n"
    "- Keep your responses short, natural, and to the point (1-2 sentences).\n"
    "- Pause and listen after each question or statement, don't rush to the next topic.\n"
    "- If the user gives a short answer, ask a follow-up or show interest before moving on.\n"
    "- Never overload the user with too much information at once.\n"
    "- Avoid long monologues.\n"
    "- Make the conversation interactive and engaging.\n"
    "- React naturally to what they say and build on it immediately.\n"
    "- Don't acknowledge every small response like 'yes', 'yeah', 'okay' - just continue naturally.\n"
    "- Don't say 'Thank you for your response' or similar formal acknowledgments.\n"
    "- If you don't understand, politely ask for clarification.\n\n"
    "KEY POINTS TO COVER:\n"
    "1. Teya provides simple, reliable, and affordable merchant services for small and medium-sized businesses.\n"
    "2. Services include card machines, fast settlements, transparent pricing, business insights, and reliable support.\n"
    "3. Focus on how Teya helps businesses grow and operate more efficiently.\n"
    "4. Be professional but friendly, and always listen to the customer's needs.\n"
    "5. If they show interest, offer to connect them with a sales representative.\n\n"
    "CONVERSATION FLOW:\n"
    "- Ask about their current payment processing setup.\n"
    "- Understand their business type and size.\n"
    "- Identify their pain points with current solutions.\n"
    "- Highlight relevant Teya features based on their needs, but only a little at a time.\n"
    "- Be prepared to discuss pricing and setup process, but only if they ask.\n\n"
    "EXAMPLES OF NATURAL RESPONSES:\n"
    "Instead of: 'Thank you for your response. Can you tell me more about your business?'\n"
    "Say: 'Great! So what kind of business are you running?'\n\n"
    "Instead of: 'I appreciate that information. What payment methods do you currently accept?'\n"
    "Say: 'Right, and how are you handling payments at the moment?'\n\n"
    "Keep it conversational, natural, and focus on building rapport while gathering information and presenting solutions.\n"
    "Remember: Use a female voice, keep it short, and make it feel like a real, friendly conversation."
)

LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created', 'conversation.item.created', 'response.audio_transcript.delta',
    'response.audio_transcript.done', 'conversation.item.input_audio_transcription.completed',
    'conversation.item.input_audio_transcription.failed'
]

class TranscriptionBuffer:
    """Buffer to store transcriptions before saving to database"""
    
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self.transcriptions: List[Dict[str, Any]] = []
        self.session_id: str = None
        self.call_log_id: int = None
    
    def add_transcription(self, speaker: str, text: str, confidence: float = None, timestamp: datetime = None):
        """Add a transcription to the buffer"""
        transcription = {
            'speaker': speaker,
            'text': text,
            'confidence': confidence,
            'timestamp': timestamp or datetime.now(),
            'is_final': True
        }
        self.transcriptions.append(transcription)
        logger.info(f"Added to buffer - {speaker}: {text[:50]}... (total: {len(self.transcriptions)})")
    
    def set_session_info(self, session_id: str, call_log_id: int):
        """Set session and call log information"""
        self.session_id = session_id
        self.call_log_id = call_log_id
    
    async def flush_to_database(self, prisma_service: PrismaService, hubspot_service=None):
        """Save all buffered transcriptions as a single JSON entry to the database"""
        if not self.transcriptions or not self.call_log_id:
            logger.warning(f"No transcriptions to save or missing call_log_id for call {self.call_sid}")
            return

        try:
            async with prisma_service:
                # Prepare the conversation as a list of dicts in the format you specified
                conversation = [
                    {
                        "speaker": t["speaker"],
                        "text": t["text"],
                        "confidence": t.get("confidence"),
                        "timestamp": t.get("timestamp").isoformat() if t.get("timestamp") else None,
                        "is_final": t.get("is_final", True)
                    }
                    for t in self.transcriptions
                ]
                
                logger.info(f"Flushing {len(conversation)} transcriptions to database for call {self.call_sid}")
                logger.info(f"Conversation JSON: {json.dumps(conversation, indent=2)}")
                
                # Save as a single transcription entry with the JSON conversation
                await prisma_service.add_transcription(
                    call_log_id=self.call_log_id,
                    speaker="conversation",
                    text=json.dumps(conversation),  # Save as JSON string
                    confidence=None,
                    session_id=self.session_id,
                    is_final=True
                )
                logger.info(f"Saved full conversation as a single JSON entry for call {self.call_sid}")

                # if hubspot_service:
                #     call_log = await prisma_service.get_call_log(self.call_sid)
                #     if call_log and call_log.toNumber:
                #         conversation_text = "\n".join(
                #             [f"{t['speaker'].capitalize()}: {t['text']}" for t in self.transcriptions]
                #         )
                #         # hubspot_service.create_note_for_contact(call_log.toNumber, conversation_text)
                #         logger.info(f"Pushed transcription as note to HubSpot for contact {call_log.toNumber}")
                #     else:
                #         logger.warning(f"No call log or phone number found for call_log_id {self.call_log_id}")
        except Exception as e:
            logger.error(f"Error flushing transcriptions to database for call {self.call_sid}: {str(e)}")
    
    def get_transcription_count(self) -> int:
        """Get the number of transcriptions in the buffer"""
        return len(self.transcriptions)
    
    def get_full_conversation(self) -> str:
        """Get the full conversation as a formatted string"""
        conversation = []
        for t in self.transcriptions:
            speaker_label = "👤 User" if t['speaker'] == 'user' else "🤖 Assistant"
            conversation.append(f"{speaker_label}: {t['text']}")
        return "\n".join(conversation)

class WebSocketService:
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key not found in environment variables")
        self.api_key = OPENAI_API_KEY
        self.prisma_service = PrismaService()
        self.hubspot_service = HubspotService()
        self.transcription_service = TranscriptionService(self.prisma_service)
        # Dictionary to store transcription buffers by call_sid
        self.transcription_buffers: Dict[str, TranscriptionBuffer] = {}
        # Dictionary to map session_id to call_sid
        self.session_to_call_mapping: Dict[str, str] = {}
        # Dictionary to map temporary call_sids to real call_sids
        self.temp_to_real_call_mapping: Dict[str, str] = {}
        # Dictionary to store pending call_sids for later mapping
        self.pending_call_sids: Dict[str, Dict[str, Any]] = {}
        logger.info("WebSocketService initialized with transcription service")

    def get_transcription_service(self):
        """Get the transcription service instance."""
        return self.transcription_service

    async def get_or_create_transcription_buffer(self, call_sid: str) -> TranscriptionBuffer:
        """Get or create a transcription buffer for a call"""
        if call_sid not in self.transcription_buffers:
            self.transcription_buffers[call_sid] = TranscriptionBuffer(call_sid)
            logger.info(f"Created transcription buffer for call {call_sid}")
            logger.debug(f"All buffers after creation: {list(self.transcription_buffers.keys())}")
            
            # Try to set up the call_log_id for the buffer
            await self._ensure_buffer_has_call_log_id(call_sid)
        else:
            logger.debug(f"Using existing transcription buffer for call {call_sid}")
            logger.debug(f"Buffer for {call_sid} has {self.transcription_buffers[call_sid].get_transcription_count()} transcriptions")
        return self.transcription_buffers[call_sid]

    async def _ensure_buffer_has_call_log_id(self, call_sid: str):
        """Ensure the transcription buffer has the proper call_log_id set up"""
        try:
            buffer = self.transcription_buffers.get(call_sid)
            if buffer and not buffer.call_log_id:
                async with self.prisma_service:
                    call_log = await self.prisma_service.get_call_log(call_sid)
                    if call_log:
                        buffer.set_session_info(None, call_log.id)
                        logger.info(f"Set up call_log_id {call_log.id} for buffer {call_sid}")
                    else:
                        logger.warning(f"Call log not found for {call_sid}, cannot set up buffer")
        except Exception as e:
            logger.error(f"Error ensuring buffer has call_log_id for {call_sid}: {str(e)}")

    def map_temp_to_real_call_sid(self, temp_call_sid: str, real_call_sid: str):
        """Map a temporary call_sid to a real call_sid"""
        self.temp_to_real_call_mapping[temp_call_sid] = real_call_sid
        logger.info(f"Mapped temporary call_sid {temp_call_sid} to real call_sid {real_call_sid}")
        
        # If we have a transcription buffer for the temp call_sid, rename it
        if temp_call_sid in self.transcription_buffers:
            buffer = self.transcription_buffers[temp_call_sid]
            self.transcription_buffers[real_call_sid] = buffer
            buffer.call_sid = real_call_sid
            del self.transcription_buffers[temp_call_sid]
            logger.info(f"Moved transcription buffer from {temp_call_sid} to {real_call_sid}")
        
        # If we have an active transcription for the temp call_sid, rename it
        if temp_call_sid in self.transcription_service.active_transcriptions:
            transcription = self.transcription_service.active_transcriptions[temp_call_sid]
            self.transcription_service.active_transcriptions[real_call_sid] = transcription
            del self.transcription_service.active_transcriptions[temp_call_sid]
            logger.info(f"Moved active transcription from {temp_call_sid} to {real_call_sid}")

    def auto_map_temp_call_sids(self, real_call_sid: str):
        """Automatically map any temp call_sid that has transcriptions to the real call_sid"""
        logger.info(f"Auto-mapping temp call_sids to real call_sid: {real_call_sid}")
        logger.info(f"Available transcription buffers: {list(self.transcription_buffers.keys())}")
        logger.info(f"Available active transcriptions: {list(self.transcription_service.active_transcriptions.keys())}")
        
        # Find any temp call_sid that has transcriptions in buffer
        for temp_call_sid in self.transcription_buffers.keys():
            if temp_call_sid.startswith("temp_call_"):
                buffer = self.transcription_buffers[temp_call_sid]
                if buffer.get_transcription_count() > 0:
                    logger.info(f"Found temp call_sid {temp_call_sid} with {buffer.get_transcription_count()} transcriptions in buffer")
                    self.map_temp_to_real_call_sid(temp_call_sid, real_call_sid)
                    return temp_call_sid
        
        # Also check active transcriptions
        for temp_call_sid in self.transcription_service.active_transcriptions.keys():
            if temp_call_sid.startswith("temp_call_"):
                transcription = self.transcription_service.active_transcriptions[temp_call_sid]
                if len(transcription.entries) > 0:
                    logger.info(f"Found temp call_sid {temp_call_sid} with {len(transcription.entries)} transcription entries in active transcriptions")
                    self.map_temp_to_real_call_sid(temp_call_sid, real_call_sid)
                    return temp_call_sid
        
        # Check completed transcriptions as well
        for temp_call_sid in self.transcription_service.completed_transcriptions.keys():
            if temp_call_sid.startswith("temp_call_"):
                transcription = self.transcription_service.completed_transcriptions[temp_call_sid]
                if len(transcription.entries) > 0:
                    logger.info(f"Found temp call_sid {temp_call_sid} with {len(transcription.entries)} transcription entries in completed transcriptions")
                    self.map_temp_to_real_call_sid(temp_call_sid, real_call_sid)
                    return temp_call_sid
        
        logger.warning(f"No temp call_sid with transcriptions found to map to {real_call_sid}")
        return None

    async def initialize_session(self, openai_ws, call_sid: str = None, to_number: str = None):
        """Initialize the OpenAI session with configuration."""
        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad","threshold": 0.5},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": VOICE,
                "instructions": SYSTEM_MESSAGE,
                "modalities": ["text", "audio"],
                "temperature": 0.7,
                "input_audio_transcription": {
                    "model": "whisper-1"
                }
            }
        }
        logger.info('Sending session update')
        logger.info(f'Session update payload: {json.dumps(session_update, indent=2)}')
        logger.info(f'{to_number=}, {call_sid=}')
        await openai_ws.send(json.dumps(session_update))
        
        # Create session in database and start transcription if call_sid is provided
        if call_sid:
            async with self.prisma_service:
                # Start transcription tracking
                self.transcription_service.start_call_transcription(call_sid)
                logger.info(f"Started transcription tracking for call {call_sid}")
                
                # Get the call log to get its ID
                call_log = await self.prisma_service.get_call_log(call_sid)
                if call_log:
                    try:
                        # Create a session ID
                        session_id = f"session_{call_sid}"
                        session = await self.prisma_service.create_session(
                            session_id=session_id,
                            model="gpt-4o-realtime-preview-2024-10-01",
                            voice=VOICE
                        )
                        # Link session to call using the session's ID (not sessionId)
                        await self.prisma_service.link_session_to_call(session.id, call_sid)
                        await self.prisma_service.update_session_status(session.id, "active")
                        
                        # Store the mapping for later use
                        self.session_to_call_mapping[session_id] = call_sid
                        logger.info(f"Stored session mapping: {session_id} -> {call_sid}")
                        
                        # Set session info in transcription buffer
                        buffer = await self.get_or_create_transcription_buffer(call_sid)
                        buffer.set_session_info(session.id, call_log.id)
                    except Exception as session_error:
                        logger.error(f"Error creating/linking session: {str(session_error)}")
                        # Continue without session linking - transcription will still work
                        buffer = await self.get_or_create_transcription_buffer(call_sid)
                        buffer.set_session_info(None, call_log.id)
        
        # Get previous call context if to_number is provided
        previous_context = ""
        if to_number:
            logger.info(f"Attempting to get previous call context for: {to_number}")
            previous_context = await self.transcription_service.get_previous_call_context(to_number, limit=2)
            if previous_context:
                logger.info(f"✅ Found previous call context for {to_number}")
                logger.info(f"Context length: {len(previous_context)} characters")
                logger.info(f"Context content: {previous_context}")
            else:
                logger.info(f"❌ No previous call context found for {to_number}")
        else:
            logger.warning("No to_number provided, cannot retrieve context")
        
        # Prepare initial greeting with context
        if previous_context:
            greeting_text = f"Hi! This is Sarah from Teya UK. We spoke recently about your payment processing needs. I have some context from our previous conversations:\n\n{previous_context}\n\nHow have things been since we last spoke? Have you made any progress with your payment processing setup?"
        else:
            # Dynamic greeting for new calls
            greeting_text = "Hi! This is Sarah from Teya UK. I'm calling about payment processing solutions for your business. Is this a good time to talk?"
        
        logger.info(f"🎯 INITIAL GREETING: {greeting_text}")
        # Send initial greeting
        initial_conversation_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": greeting_text
                    }
                ]
            }
        }
        logger.info(f'Sending initial conversation item: {json.dumps(initial_conversation_item, indent=2)}')
        await openai_ws.send(json.dumps(initial_conversation_item))
        logger.info('Sending response.create')
        await openai_ws.send(json.dumps({"type": "response.create"}))

    async def handle_speech_started_event(self, openai_ws, websocket, stream_sid, response_start_timestamp_twilio, 
                                        last_assistant_item, latest_media_timestamp, mark_queue):
        """Handle interruption when the caller's speech starts."""
        logger.info("Handling speech started event")
        if mark_queue and response_start_timestamp_twilio is not None:
            elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
            logger.debug(f"Calculating elapsed time for truncation: {elapsed_time}ms")

            if last_assistant_item:
                logger.debug(f"Truncating item with ID: {last_assistant_item}")
                truncate_event = {
                    "type": "conversation.item.truncate",
                    "item_id": last_assistant_item,
                    "content_index": 0,
                    "audio_end_ms": elapsed_time
                }
                await openai_ws.send(json.dumps(truncate_event))

            await websocket.send_json({
                "event": "clear",
                "streamSid": stream_sid
            })

            mark_queue.clear()
            last_assistant_item = None
            response_start_timestamp_twilio = None

    async def send_mark(self, connection, stream_sid, mark_queue):
        """Send a mark event to the stream."""
        if stream_sid:
            mark_event = {
                "event": "mark",
                "streamSid": stream_sid,
                "mark": {"name": "responsePart"}
            }
            await connection.send_json(mark_event)
            mark_queue.append('responsePart')
            logger.debug("Sent mark event")

    async def process_openai_message(self, call_sid: str, message: dict, current_session_id: str = None):
        """Process OpenAI WebSocket message and collect transcriptions for batch saving."""
        try:
            # If call_sid is not provided, try to get it from session mapping
            if not call_sid and current_session_id:
                call_sid = self.session_to_call_mapping.get(current_session_id)
                if call_sid:
                    logger.info(f"Retrieved call_sid {call_sid} from session mapping for session {current_session_id}")
            
            # If still no call_sid, try to extract from message
            if not call_sid and "session" in message and "id" in message["session"]:
                session_id = message["session"]["id"]
                call_sid = self.session_to_call_mapping.get(session_id)
                if call_sid:
                    logger.info(f"Retrieved call_sid {call_sid} from session mapping for session {session_id}")
            
            # Use the transcription service to process the message
            if call_sid:
                self.transcription_service.process_openai_message(call_sid, message)
                
                # Also add to transcription buffer for batch saving
                buffer = await self.get_or_create_transcription_buffer(call_sid)
                message_type = message.get("type")
                
                logger.debug(f"Processing message type '{message_type}' for call {call_sid} in buffer")
                logger.debug(f"Buffer for {call_sid} currently has {buffer.get_transcription_count()} transcriptions")
                logger.debug(f"All available buffers: {list(self.transcription_buffers.keys())}")
                
                # Handle completed user transcriptions
                if message_type == "conversation.item.input_audio_transcription.completed":
                    transcript = message.get("transcript", "")
                    confidence = message.get("confidence")
                    if transcript:
                        buffer.add_transcription(
                            speaker="user",
                            text=transcript,
                            confidence=confidence
                        )
                        logger.info(f"Added user transcription to buffer: {transcript[:50]}... (total: {buffer.get_transcription_count()})")
                        logger.debug(f"After adding user transcription, buffer for {call_sid} has {buffer.get_transcription_count()} transcriptions")
                        
                        # Also save directly to database as backup
                        await self.save_transcription_to_database_direct(call_sid, "user", transcript, confidence)
                
                # Handle assistant audio transcriptions
                elif message_type == "response.audio_transcript.done":
                    transcript = message.get("transcript", "")
                    confidence = message.get("confidence")
                    if transcript:
                        buffer.add_transcription(
                            speaker="assistant",
                            text=transcript,
                            confidence=confidence
                        )
                        logger.info(f"Added assistant transcription to buffer: {transcript[:50]}... (total: {buffer.get_transcription_count()})")
                        logger.debug(f"After adding assistant transcription, buffer for {call_sid} has {buffer.get_transcription_count()} transcriptions")
                        
                        # Also save directly to database as backup
                        await self.save_transcription_to_database_direct(call_sid, "assistant", transcript, confidence)
                
                # Handle text responses (for text-based assistant responses)
                elif message_type == "response.content.done":
                    content = message.get("content", [])
                    for content_item in content:
                        if content_item.get("type") == "text":
                            text = content_item.get("text", "")
                            if text:
                                buffer.add_transcription(
                                    speaker="assistant",
                                    text=text
                                )
                                logger.info(f"Added text response to buffer: {text[:50]}... (total: {buffer.get_transcription_count()})")
                                logger.debug(f"After adding text response, buffer for {call_sid} has {buffer.get_transcription_count()} transcriptions")
                                
                                # Also save directly to database as backup
                                await self.save_transcription_to_database_direct(call_sid, "assistant", text)
            else:
                logger.warning(f"No call_sid available for message: {message.get('type', 'unknown')}")
                # Try to extract call_sid from the message itself or use a fallback
                if "session" in message and "id" in message["session"]:
                    session_id = message["session"]["id"]
                    logger.info(f"Found session ID in message: {session_id}")
                    # Could potentially map session_id to call_sid if we track this
                
        except Exception as e:
            logger.error(f"Error processing OpenAI message for transcription: {str(e)}")

    async def save_transcription_to_database(self, call_sid: str, speaker: str, text: str, confidence: float = None):
        """Save transcription directly to database (legacy method - now using buffer approach)."""
        try:
            # Instead of saving immediately, add to buffer for batch saving
            buffer = await self.get_or_create_transcription_buffer(call_sid)
            buffer.add_transcription(speaker, text, confidence)
            logger.info(f"Added transcription to buffer for batch saving: {speaker} - {text[:50]}...")
        except Exception as e:
            logger.error(f"Error adding transcription to buffer: {str(e)}")

    async def save_transcription_to_database_direct(self, call_sid: str, speaker: str, text: str, confidence: float = None):
        """Save transcription directly to database as backup."""
        try:
            async with self.prisma_service:
                # Get the call log
                call_log = await self.prisma_service.get_call_log(call_sid)
                if call_log:
                    # Save transcription directly to database
                    await self.prisma_service.add_transcription(
                        call_log_id=call_log.id,
                        speaker=speaker,
                        text=text,
                        confidence=confidence,
                        session_id=None,  # We'll handle session linking separately
                        is_final=True
                    )
                    logger.debug(f"Saved transcription directly to database: {speaker} - {text[:50]}...")
                else:
                    logger.warning(f"Call log not found for {call_sid}, cannot save transcription directly")
        except Exception as e:
            logger.error(f"Error saving transcription directly to database: {str(e)}")

    async def finalize_call_transcriptions(self, call_sid: str):
        """Save all buffered transcriptions to database when call ends"""
        try:
            logger.info(f"Finalizing transcriptions for call {call_sid}")
            logger.info(f"Available transcription buffers: {list(self.transcription_buffers.keys())}")
            logger.info(f"Available temp mappings: {self.temp_to_real_call_mapping}")
            logger.info(f"Session to call mappings: {self.session_to_call_mapping}")
            
            # Check for any temp call_sids that might have transcriptions but aren't mapped yet
            found_transcriptions = False
            transcription_call_sid = call_sid
            
            # First, try to find any temp call_sid with transcriptions
            for temp_sid, buffer in self.transcription_buffers.items():
                if temp_sid.startswith("temp_call_") and buffer.get_transcription_count() > 0:
                    logger.info(f"Found temp call_sid {temp_sid} with {buffer.get_transcription_count()} transcriptions")
                    # Map this temp call_sid to the real call_sid
                    self.map_temp_to_real_call_sid(temp_sid, call_sid)
                    transcription_call_sid = temp_sid
                    found_transcriptions = True
                    break
            
            # If no temp call_sid found, check if this call_sid has a temp mapping
            if not found_transcriptions:
                temp_call_sid = None
                for temp_sid, real_sid in self.temp_to_real_call_mapping.items():
                    if real_sid == call_sid:
                        temp_call_sid = temp_sid
                        break
                
                if temp_call_sid and temp_call_sid in self.transcription_buffers:
                    transcription_call_sid = temp_call_sid
                    found_transcriptions = True
                    logger.info(f"Using existing temp mapping: {temp_call_sid} -> {call_sid}")
            
            # If still no transcriptions found, check if the real call_sid has transcriptions directly
            if not found_transcriptions and call_sid in self.transcription_buffers:
                buffer = self.transcription_buffers[call_sid]
                if buffer.get_transcription_count() > 0:
                    logger.info(f"Found transcriptions directly under real call_sid {call_sid} with {buffer.get_transcription_count()} transcriptions")
                    transcription_call_sid = call_sid
                    found_transcriptions = True
            
            # If still no transcriptions found, check if any buffer has transcriptions (fallback)
            if not found_transcriptions:
                for buffer_sid, buffer in self.transcription_buffers.items():
                    if buffer.get_transcription_count() > 0:
                        logger.info(f"Found transcriptions in buffer {buffer_sid} with {buffer.get_transcription_count()} transcriptions")
                        transcription_call_sid = buffer_sid
                        found_transcriptions = True
                        break
            
            logger.info(f"Using transcription call_sid: {transcription_call_sid}")
            
            # Now end the transcription service properly
            if transcription_call_sid in self.transcription_service.active_transcriptions:
                logger.info(f"Ending transcription service for call {transcription_call_sid}")
                await self.transcription_service.end_call_transcription(transcription_call_sid)
            
            # Also handle the buffer as backup
            if transcription_call_sid in self.transcription_buffers:
                buffer = self.transcription_buffers[transcription_call_sid]
                
                logger.info(f"Finalizing transcriptions for call {call_sid}. Buffer contains {buffer.get_transcription_count()} transcriptions")
                
                # Save to database
                await buffer.flush_to_database(self.prisma_service)
                
                # Log the full conversation for debugging
                if buffer.get_transcription_count() > 0:
                    logger.info(f"Full conversation for call {call_sid}:\n{buffer.get_full_conversation()}")
                
                # Clean up the buffer
                del self.transcription_buffers[transcription_call_sid]
                logger.info(f"Cleaned up transcription buffer for call {call_sid}")
                found_transcriptions = True
            else:
                logger.warning(f"No transcription buffer found for call {call_sid} (or temp call_sid {transcription_call_sid})")
                logger.warning(f"Available buffers: {list(self.transcription_buffers.keys())}")
                
                # Check if transcriptions were saved directly to database
                try:
                    async with self.prisma_service:
                        call_log = await self.prisma_service.get_call_log(call_sid)
                        if call_log:
                            transcriptions = await self.prisma_service.get_transcriptions_for_call(call_log.id)
                            if transcriptions:
                                logger.info(f"Found {len(transcriptions)} transcriptions already saved to database for call {call_sid}")
                                
                                # Create a JSON conversation entry from the individual transcriptions
                                conversation_data = []
                                for t in transcriptions:
                                    conversation_data.append({
                                        "speaker": t.speaker,
                                        "text": t.text,
                                        "confidence": t.confidence,
                                        "timestamp": t.created_at.isoformat() if t.created_at else None,
                                        "is_final": True
                                    })
                                
                                # Save as JSON conversation entry
                                if conversation_data:
                                    conversation_json = json.dumps(conversation_data, indent=2)
                                    logger.info(f"Creating JSON conversation entry with {len(conversation_data)} transcriptions")
                                    
                                    # Update the call log with the conversation JSON
                                    await self.prisma_service.update_call_log(
                                        call_sid=call_sid,
                                        conversation_json=conversation_json
                                    )
                                    logger.info(f"Saved conversation as JSON for call {call_sid}")
                                
                                found_transcriptions = True
                            else:
                                logger.warning(f"No transcriptions found in database for call {call_sid}")
                        else:
                            logger.warning(f"Call log not found for {call_sid}")
                except Exception as e:
                    logger.error(f"Error checking database transcriptions for call {call_sid}: {str(e)}")
            
            if not found_transcriptions:
                logger.warning(f"No transcriptions found for call {call_sid}")
                
        except Exception as e:
            logger.error(f"Error finalizing transcriptions for call {call_sid}: {str(e)}")

    async def handle_media_stream(self, websocket, openai_ws, call_sid: str = None):
        """Handle the media stream between Twilio and OpenAI."""
        try:
            # Connection specific state
            stream_sid = None
            latest_media_timestamp = 0
            last_assistant_item = None
            mark_queue = []
            response_start_timestamp_twilio = None
            current_session_id = None

            async def receive_from_twilio():
                nonlocal stream_sid, latest_media_timestamp
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        logger.debug(f"Received from Twilio: {data['event']}")
                        
                        if data['event'] == 'media' and openai_ws.open:
                            latest_media_timestamp = int(data['media']['timestamp'])
                            audio_append = {
                                "type": "input_audio_buffer.append",
                                "audio": data['media']['payload']
                            }
                            await openai_ws.send(json.dumps(audio_append))
                            logger.debug("Sent audio chunk to OpenAI")
                        elif data['event'] == 'start':
                            stream_sid = data['start']['streamSid']
                            logger.info(f"Incoming stream has started {stream_sid}")
                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None
                        elif data['event'] == 'mark':
                            if mark_queue:
                                mark_queue.pop(0)
                                logger.debug("Processed mark event")
                except Exception as e:
                    logger.error(f"Error in receive_from_twilio: {str(e)}")
                    if openai_ws.open:
                        await openai_ws.close()

            async def send_to_twilio():
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, current_session_id
                try:
                    async for openai_message in openai_ws:
                        response = json.loads(openai_message)
                        
                        # Log ALL OpenAI messages for debugging
                        logger.info(f"🔍 OPENAI MESSAGE: {response.get('type', 'unknown')} - {json.dumps(response)[:200]}...")
                        
                        # Log important events
                        if response['type'] in LOG_EVENT_TYPES:
                            logger.info(f"Received OpenAI event: {response['type']}")
                        
                        # Handle error events specifically
                        if response.get('type') == 'error':
                            error_details = response.get('error', {})
                            logger.error(f"❌ OPENAI ERROR: {error_details}")
                        
                        # LOG TRANSCRIPTION CONTENT HERE
                        # Handle assistant transcription deltas (what the AI is saying)
                        if response.get('type') == 'response.audio_transcript.delta':
                            delta_text = response.get('delta', '')
                            if delta_text:
                                logger.info(f"🤖 ASSISTANT SPEAKING: {delta_text}")
                        
                        # Handle completed assistant transcriptions
                        elif response.get('type') == 'response.audio_transcript.done':
                            transcript = response.get('transcript', '')
                            if transcript:
                                logger.info(f"🤖 ASSISTANT COMPLETE: {transcript}")
                        
                        # Handle user transcriptions (what the caller is saying)
                        elif response.get('type') == 'conversation.item.input_audio_transcription.completed':
                            transcript = response.get('transcript', '')
                            if transcript:
                                logger.info(f"👤 USER SAID: {transcript}")
                        
                        # Handle failed transcriptions
                        elif response.get('type') == 'conversation.item.input_audio_transcription.failed':
                            error = response.get('error', {})
                            logger.warning(f"❌ TRANSCRIPTION FAILED: {error}")
                        
                        # Process message for transcription buffer if we have a call_sid
                        if call_sid:
                            await self.process_openai_message(call_sid, response, current_session_id)
                            logger.debug(f"Processed message for call {call_sid}: {response.get('type', 'unknown')}")
                        else:
                            await self.process_openai_message(None, response, current_session_id)
                            logger.warning(f"No call_sid available for message: {response.get('type', 'unknown')}")
                        
                        # Handle session creation
                        if response.get('type') == 'session.created':
                            current_session_id = response.get('session', {}).get('id')
                            logger.info(f"Session created with ID: {current_session_id}")
                            
                            # If we have a call_sid, store the mapping
                            if call_sid and current_session_id:
                                self.session_to_call_mapping[current_session_id] = call_sid
                                logger.info(f"Updated session mapping: {current_session_id} -> {call_sid}")
                        
                        # Handle audio responses
                        if response.get('type') == 'response.audio.delta' and 'delta' in response:
                            audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                            audio_delta = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
                                }
                            }
                            await websocket.send_json(audio_delta)
                            logger.debug("Sent audio response to Twilio")
                            
                            if response_start_timestamp_twilio is None:
                                response_start_timestamp_twilio = latest_media_timestamp
                            
                            if response.get('item_id'):
                                last_assistant_item = response['item_id']
                            
                            await self.send_mark(websocket, stream_sid, mark_queue)
                        
                        # Handle speech detection
                        if response.get('type') == 'input_audio_buffer.speech_started':
                            logger.info("🎤 Speech started detected")
                            if last_assistant_item:
                                await self.handle_speech_started_event(
                                    openai_ws, websocket, stream_sid,
                                    response_start_timestamp_twilio,
                                    last_assistant_item,
                                    latest_media_timestamp,
                                    mark_queue
                                )
                        
                        # Handle speech stopped
                        if response.get('type') == 'input_audio_buffer.speech_stopped':
                            logger.info("🛑 Speech stopped detected")
                        
                        # Handle session end
                        if response.get('type') == 'session.ended':
                            if current_session_id:
                                async with self.prisma_service:
                                    # Find the session by sessionId and update its status
                                    try:
                                        await self.prisma_service.update_session_status_by_session_id(current_session_id, "completed")
                                    except Exception as e:
                                        logger.error(f"Error updating session status: {str(e)}")
                            
                            # End transcription tracking and save to database
                            if call_sid:
                                await self.transcription_service.end_call_transcription(call_sid)
                                # Also finalize transcriptions here to ensure they're saved
                                await self.finalize_call_transcriptions(call_sid)
                            
                            logger.info("Session ended")
                            
                except Exception as e:
                    logger.error(f"Error in send_to_twilio: {str(e)}")

            await asyncio.gather(receive_from_twilio(), send_to_twilio())
            
        except Exception as e:
            logger.error(f"Error in media stream: {str(e)}")
            raise
        finally:
            # Ensure transcription is ended and saved when connection closes
            if call_sid:
                await self.transcription_service.end_call_transcription(call_sid)
                await self.finalize_call_transcriptions(call_sid)
                logger.info(f"Finalized transcription tracking for call {call_sid} due to connection close")