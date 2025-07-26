import json
import base64
import asyncio
import websockets
import logging
from config import OPENAI_API_KEY
from services.prisma_service import PrismaService
from services.hubspot_service import HubspotService
from services.transcription_service import TranscriptionService, SpeakerType
from services.context_service import ContextService
from typing import List, Dict, Any, Optional
from datetime import datetime
import openai

logger = logging.getLogger(__name__)

# --- GLOBAL/MODULE-LEVEL DICTIONARY FOR LIVE CONVERSATIONS ---
GLOBAL_LIVE_CONVERSATION_BUFFERS: Dict[str, 'TranscriptionBuffer'] = {}
# -----------------------------------------------------------

# OpenAI Configuration
VOICE = 'echo'
TEMPERATURE = 0.7

SYSTEM_MESSAGE = (
    "You are a sales representative for Teya UK, a payment solutions company. "
    "IMPORTANT: You must speak first immediately when the call starts. Do not wait for the user to speak.\n"
    "Your goal is to learn about their business and offer payment solutions.\n"
    "SPEECH CONTROL - VERY IMPORTANT:\n"
    "- Speak at a SLOW, natural, conversational pace. Do NOT rush.\n"
    "- Use natural pauses between sentences and phrases.\n"
    "- Keep responses very short (1-2 sentences maximum per response).\n"
    "- Never ask more than one question at a time.\n"
    "- If the user says 'thank you' or wants to end the call, simply say 'Thanks, goodbye!' and stop.\n"
    "- Do NOT give long farewell speeches or offer future assistance.\n"
    "- Keep all responses under 15 words when possible.\n"
    "CONTEXT AWARENESS:\n"
    "- If this is a callback or repeat customer, acknowledge it naturally in your greeting.\n"
    "- Reference their business type if you know it.\n"
    "- Don't repeat information gathering if you already have context about them.\n"
    "INTERRUPTION HANDLING:\n"
    "- IMMEDIATELY stop speaking when the user starts talking.\n"
    "- Never continue your previous thought after being interrupted.\n"
    "- Listen to what the user says and respond directly to their input.\n"
    "- Always prioritize responding to user input over completing your own thoughts.\n"
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
        self.entries: List[Dict[str, Any]] = []  # Renamed from 'transcriptions' to 'entries' for clarity
        self.session_db_id: Optional[str] = None # Store CUID string
        self.call_log_db_id: Optional[int] = None  # Store the Prisma DB ID for the call_log
        self.start_time = datetime.now()  # Track start time of the conversation
        self.end_time = None  # Track end time
        logger.debug(f"TranscriptionBuffer created for call_sid: {call_sid}")
    
    def add_entry(self, speaker: str, text: str, is_final: bool = False, timestamp: datetime = None):
        """Add a transcription entry to the buffer"""
        entry = {
            'speaker': speaker,
            'text': text,
            'timestamp': timestamp.isoformat() if timestamp else datetime.now().isoformat(),  # Store as ISO string
            'is_final': is_final
        }
        self.entries.append(entry)
        logger.debug(f"Added to buffer - {speaker}: {text[:50]}...")
    
    def set_db_ids(self, session_db_id: str, call_log_db_id: int):
        """Set database IDs for session and call log"""
        self.session_db_id = session_db_id # Store CUID string
        self.call_log_db_id = call_log_db_id
        logger.debug(f"Set DB IDs for call {self.call_sid}: CallLogID={self.call_log_db_id}, SessionDBID={self.session_db_id}")

    def get_entry_count(self) -> int:
        """Get the number of transcription entries in the buffer"""
        return len(self.entries)
    
    def get_full_conversation_text(self) -> str:
        """Get the full conversation as a formatted string"""
        conversation = []
        for t in self.entries:
            speaker_label = "👤 User" if t['speaker'] == 'user' else "🤖 Assistant"
            conversation.append(f"{speaker_label}: {t['text']}")
        return "\n".join(conversation)

    def set_end_time(self):
        self.end_time = datetime.now()
    
    @property
    def total_duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self):
        return {
            "call_sid": self.call_sid,
            "call_log_db_id": self.call_log_db_id,
            "session_db_id": self.session_db_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration": self.total_duration,
            "entries": self.entries  # Contains speaker, text, timestamp, is_final
        }

class WebSocketService:
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key not found in environment variables")
        self.api_key = OPENAI_API_KEY
        self.transcription_service = TranscriptionService()
        self.hubspot_service = HubspotService()
        self.prisma_service = PrismaService()
        self.context_service = ContextService()
        # No more self.live_conversation_buffers here; use GLOBAL_LIVE_CONVERSATION_BUFFERS
        logger.info(f"WebSocketService initialized (ID: {id(self)}) with access to global in-memory buffer")

    def get_transcription_service(self):
        """Get the transcription service instance."""
        return self.transcription_service

    def get_or_create_buffer(self, call_sid: str) -> TranscriptionBuffer:
        if call_sid not in GLOBAL_LIVE_CONVERSATION_BUFFERS:
            GLOBAL_LIVE_CONVERSATION_BUFFERS[call_sid] = TranscriptionBuffer(call_sid)
            logger.info(f"Created new TranscriptionBuffer in GLOBAL_LIVE_CONVERSATION_BUFFERS for call {call_sid}")
        return GLOBAL_LIVE_CONVERSATION_BUFFERS[call_sid]

    async def initialize_session(self, openai_ws, call_sid: str = None, phone_number: str = None):
        """Initialize the OpenAI session with configuration and context-aware instructions."""
        voice_future = self.prisma_service.get_constant("VOICE")
        instructions_future = self.prisma_service.get_constant("SYSTEM_MESSAGE")
        temp_future = self.prisma_service.get_constant("TEMPERATURE")

        results = await asyncio.gather(
            voice_future,
            instructions_future,
            temp_future
        )
        voice, instructions, temp_str = results
        try:
            # Provide a default value and ensure temperature is a float
            temperature = float(temp_str.value) if temp_str is not None else 0.3  # Lower temperature for more controlled speech
        except (ValueError, TypeError):
            # Handle cases where the stored value is not a valid number
            temperature = 0.3  # Lower temperature for more stable responses

        # Get base instructions
        base_instructions = instructions.value if instructions else SYSTEM_MESSAGE
        
        # Get context-aware instructions if phone number is available
        context_instructions = base_instructions
        call_context = None
        
        logger.info(f"[CONTEXT DEBUG] Phone number received: {phone_number}")
        
        if phone_number:
            try:
                # Get call history and context for this phone number
                logger.info(f"Getting context for phone number: {phone_number}")
                async with self.prisma_service:
                    call_context = await self.prisma_service.get_contact_context_by_phone(phone_number)
                    logger.info(f"[CONTEXT DEBUG] Retrieved call_context: {call_context}")
                    
                if call_context and call_context.get('call_history'):
                    logger.info(f"[CONTEXT DEBUG] Found {len(call_context['call_history'])} calls in history")
                    # Extract context from call history
                    context = self.context_service.extract_context_from_call_history(call_context['call_history'])
                    logger.info(f"[CONTEXT DEBUG] Extracted context: {context}")
                    
                    # Add simple context to system message
                    if context.get('total_calls', 0) > 0:
                        context_addition = f"\n\nIMPORTANT CONTEXT: This customer has called {context.get('total_calls')} times before. "
                        if context.get('business_type'):
                            context_addition += f"They run a {context.get('business_type')} business. "
                        if any('callback' in insight.lower() for insight in context.get('key_insights', [])):
                            context_addition += "This is a callback - they were busy before. "
                        context_addition += "Acknowledge this context in your greeting appropriately."
                        
                        context_instructions = base_instructions + context_addition
                        logger.info(f"Added context to instructions: {context.get('business_type')}, calls: {context.get('total_calls')}")
                        logger.info(f"[CONTEXT DEBUG] Full context_addition: {context_addition}")
                    else:
                        logger.info(f"[CONTEXT DEBUG] No calls found in context (total_calls: {context.get('total_calls', 0)})")
                    
                else:
                    logger.info(f"No call history found for {phone_number}, using base instructions")
                    logger.info(f"[CONTEXT DEBUG] call_context details: {call_context}")
                    
            except Exception as e:
                logger.error(f"Error getting context for {phone_number}: {str(e)}")
                logger.info("Falling back to base instructions")

        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad","threshold": 0.5},  # Adjusted threshold for better interruption detection
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": voice.value if voice else VOICE,
                "instructions": context_instructions,
                "modalities": ["text", "audio"],
                "temperature": temperature,
                "max_response_output_tokens": 150,  # Limit response length to prevent long speeches
                "input_audio_transcription": {
                    "model": "whisper-1"
                }
            }
        }
        logger.info('Sending session update with context-aware instructions')
        await openai_ws.send(json.dumps(session_update))
        
        # Start database operations in the background to avoid blocking
        if call_sid:
            asyncio.create_task(self._handle_database_setup(call_sid, openai_ws))
        
        # Return context for use in greeting
        return call_context

    async def _handle_database_setup(self, call_sid: str, openai_ws):
        """Handle database setup operations in the background to avoid blocking conversation start."""
        try:
            # Get or create the buffer immediately
            current_buffer = self.get_or_create_buffer(call_sid)

            async with self.prisma_service:
                # Start transcription tracking
                self.transcription_service.start_call_transcription(call_sid)
                logger.info(f"Started transcription tracking for call {call_sid}")
                
                # Get the call log to get its ID
                call_log = await self.prisma_service.get_call_log(call_sid)
                if call_log:
                    # Create session entry in DB
                    session_db_instance = await self.prisma_service.create_session(
                        session_id=f"session_{call_sid}",  # A unique string ID for the session
                        model="gpt-4o-realtime-preview-2024-10-01",
                        voice=VOICE
                    )
                    await self.prisma_service.link_session_to_call(session_db_instance.id, call_sid)  # Use session.id (CUID)
                    await self.prisma_service.update_session_status(session_db_instance.sessionId, "active")  # Use the string sessionId here
                    current_buffer.set_db_ids(session_db_id=session_db_instance.id, call_log_db_id=call_log.id) # Store CUID string
                    logger.info(f"DB session (CUID: {session_db_instance.id}) and call_log IDs set in buffer for call {call_sid}")
                else:
                    logger.warning(f"CallLog not found for {call_sid} during session initialization. Transcriptions may not be linked correctly.")
        except Exception as db_error:
            logger.warning(f"Database error during session/calllog initialization for call {call_sid}: {str(db_error)}")
            logger.warning("Continuing with call but transcription might not be saved to DB.")

    async def trigger_initial_conversation(self, openai_ws, context: Dict[str, Any] = None):
        """Trigger the initial conversation after the stream is established."""
        try:
            # Simple context-aware greeting logic
            if context and context.get('total_calls', 0) > 0:
                # This is a repeat customer - use callback greeting
                if any('callback' in insight.lower() for insight in context.get('key_insights', [])):
                    greeting_text = "Say: 'Hi, this is Teya UK calling back. Is now a better time?'"
                elif context.get('business_type'):
                    greeting_text = f"Say: 'Hi, this is Teya UK again. How's the {context.get('business_type')} business going?'"
                else:
                    greeting_text = "Say: 'Hi, this is Teya UK calling back. How are things?'"
                logger.info(f"Using callback greeting for repeat customer (calls: {context.get('total_calls')})")
            else:
                # First-time caller - standard greeting
                greeting_text = "Say: 'Hi, this is Teya UK. What kind of business do you run?'"
                logger.info("Using standard greeting for first-time caller")
            
            logger.info(f"Sending greeting: {greeting_text}")
            
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
            await openai_ws.send(json.dumps(initial_conversation_item))
            await openai_ws.send(json.dumps({"type": "response.create"}))
            logger.info('Sent context-aware greeting trigger to start AI conversation immediately')
        except Exception as e:
            logger.error(f"Error triggering initial conversation: {e}")

    def _build_context_aware_greeting(self, context: Dict[str, Any]) -> str:
        """Build a context-aware greeting based on previous conversations"""
        # Check if this is a callback situation
        insights = context.get('key_insights', [])
        is_callback = any('callback' in insight.lower() or 'busy' in insight.lower() for insight in insights)
        
        business_type = context.get('business_type', '')
        business_name = context.get('business_name', '')
        payment_prefs = context.get('payment_preferences', [])
        
        if is_callback and business_type:
            # Callback with known business
            if 'technology' in business_type or 'agency' in business_type:
                return "Say: 'Hi, this is Teya UK calling back. Is now a better time to chat?'"
            else:
                return f"Say: 'Hi, this is Teya UK calling back. Is now a good time?'"
        elif business_type and payment_prefs:
            # Known customer with payment preferences
            return f"Say: 'Hi, this is Teya UK again. How are your payments going?'"
        elif business_type:
            # Known business type but no specific callback
            return f"Say: 'Hi, this is Teya UK. How are things going?'"
        else:
            # Fallback for repeat customer without much context
            return "Say: 'Hi, this is Teya UK calling back. How can we help?'"

    async def handle_speech_started_event(self, openai_ws, websocket, stream_sid, response_start_timestamp_twilio, 
                                        last_assistant_item, latest_media_timestamp, mark_queue):
        """Handle interruption when the caller's speech starts."""
        logger.info("🎤 User started speaking - handling interruption immediately")
        
        # Immediately clear the outgoing audio to stop the AI from speaking
        if stream_sid:
            await websocket.send_json({
                "event": "clear",
                "streamSid": stream_sid
            })
            logger.info("🛑 Cleared outgoing audio stream to stop AI speech")
        
        # Calculate truncation point and truncate the current response
        if mark_queue and response_start_timestamp_twilio is not None and last_assistant_item:
            elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
            logger.info(f"Truncating AI response at {elapsed_time}ms to handle user interruption")

            truncate_event = {
                "type": "conversation.item.truncate",
                "item_id": last_assistant_item,
                "content_index": 0,
                "audio_end_ms": elapsed_time
            }
            await openai_ws.send(json.dumps(truncate_event))
            logger.info(f"Sent truncation event for item {last_assistant_item}")

        # Reset state immediately
        mark_queue.clear()
        logger.info("🔄 Reset conversation state for user input processing")

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
        logger.info(f"[OpenAI] Received event type: {message.get('type')}, message: {message.get('transcript')[:50] if message.get('transcript') else 'N/A'}")
        
        # Call the transcription_service first, as it maintains active_transcriptions
        self.transcription_service.process_openai_message(call_sid, message)

        # Buffer parts to in-memory for eventual persistence
        if call_sid:
            current_buffer = self.get_or_create_buffer(call_sid)  # Get the buffer for this call_sid
            
            message_type = message.get("type")
            transcript_text = message.get("transcript", "")
            
            # Determine if this is a final segment
            is_final_segment = False
            if message_type == "response.audio_transcript.done" or \
               message_type == "conversation.item.input_audio_transcription.completed":
                is_final_segment = True
            
            if transcript_text:
                speaker_type = "assistant" if message_type.startswith("response.audio") else "user"
                current_buffer.add_entry(speaker=speaker_type, text=transcript_text, is_final=is_final_segment)
                logger.debug(f"Buffered to in-memory for {call_sid} - {speaker_type}: {transcript_text[:50]}...")
        else:
            logger.error(f"process_openai_message: received message with no call_sid. Message type: {message.get('type')}")

    async def finalize_call_transcriptions(self, call_sid: str):
        logger.info(f"Attempting to finalize transcriptions for call {call_sid} (WS Service ID: {id(self)})")
        buffer = GLOBAL_LIVE_CONVERSATION_BUFFERS.get(call_sid)
        if not buffer or not buffer.entries:
            logger.warning(f"No buffered transcription data found in GLOBAL_LIVE_CONVERSATION_BUFFERS for call {call_sid}. Nothing to save.")
            if call_sid in GLOBAL_LIVE_CONVERSATION_BUFFERS:
                del GLOBAL_LIVE_CONVERSATION_BUFFERS[call_sid]
            return
        buffer.set_end_time()
        call_log_id = buffer.call_log_db_id
        try:
            async with self.prisma_service:
                # Always fetch the call log to get the phone number
                call_log = await self.prisma_service.get_call_log(call_sid)
                if not call_log:
                    logger.error(f"Could not find call log for {call_sid}. Cannot save transcriptions or create HubSpot note.")
                    return
                call_log_id = call_log.id
                buffer.call_log_db_id = call_log_id
        except Exception as e:
            logger.error(f"Error fetching call log for {call_sid}: {e}")
            return
        phone_number = getattr(call_log, "toNumber", None)
        transcript_json = json.dumps(buffer.entries)
        confidence_score = None
        try:
            # 1. Save the transcript JSON (without confidence) to the DB
            async with self.prisma_service:
                transcription_row = await self.prisma_service.prisma.transcription.create(
                    data={
                        'callLogId': call_log_id,
                        'transcript': transcript_json
                    }
                )
                logger.info(f"Saved single JSON transcript for call {call_sid} to DB.")
                await self.prisma_service.update_call_status(
                    call_sid=call_sid,
                    status="completed",
                    duration=int(buffer.total_duration) if buffer.total_duration is not None else None
                )
                logger.info(f"Updated CallLog {call_sid} with duration and end time.")
            conclusion = None  # Initialize as None instead of empty string
            # 2. Ask OpenAI/GPT for a confidence score for the call (new API)
            try:
                # Use only api_key, do not pass proxies or other kwargs
                client = openai.OpenAI(api_key=self.api_key)  # v1.x API, no proxies arg
                system_prompt = (
                    "You are an expert call quality analyst. You will be given a call transcription "
                    "as a JSON array of utterances. Your task is to rate the overall confidence/clarity "
                    "of the transcription and provide a brief conclusion about the user's interest. "
                    "Make sure to include the points like user wants to set a meeting, and all relevant details."
                    "You must return ONLY a single valid JSON object with two keys: 'score' (a number from 1 to 10) "
                    "and 'conclusion' (a string)."
                )
                user_prompt = f"Call transcription: {transcript_json}"
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=150,
                    temperature=0.0,
                    response_format={
                        "type": "json_object"
                    }
                )
                response_content = response.choices[0].message.content
                logger.info(f"Raw OpenAI response: {response_content}")
                data = json.loads(response_content)

                confidence_score = data.get('score')
                conclusion = data.get('conclusion')
                logger.info(f"[CONCLUSION DEBUG] Extracted from OpenAI - score: {confidence_score}, conclusion: {conclusion}")
                try:
                    confidence_score = float(confidence_score)
                    logger.info(f"OpenAI conclusion for call {call_sid}: {conclusion}")
                    logger.info(f"OpenAI confidence score for call {call_sid}: {confidence_score}")
                except Exception as parse_err:
                    logger.warning(f"Could not parse confidence score from OpenAI: '{confidence_score}' ({parse_err})")
            except Exception as openai_err:
                logger.error(f"Error getting confidence score from OpenAI: {openai_err}")
            # 3. Update the DB row with the confidence score
            if phone_number and transcript_json:
                conversation_text = "\n".join(
                    [f"{t['speaker'].capitalize()}: {t['text']}" for t in buffer.entries]
                )
                logger.info(f"Creating note for contact with phone {phone_number} in HubSpot")
                logger.debug(f"Note content: {conversation_text[:100]}...")  # Log first 100 chars for brevity
                try:
                    self.hubspot_service.create_note_for_contact(phone_number=phone_number, transcription=conversation_text, note_content=conclusion)
                except Exception as e:
                    logger.error(f"Error creating HubSpot note for {phone_number}: {e}")
            
            logger.info(f"[CONCLUSION DEBUG] Before DB update - confidence_score: {confidence_score}, conclusion: {conclusion[:50] if conclusion else 'None'}...")
            if confidence_score is not None or conclusion is not None:
                async with self.prisma_service:
                    update_data = {}
                    if confidence_score is not None:
                        update_data["confidenceScore"] = confidence_score
                        logger.info(f"[CONCLUSION DEBUG] Added confidence_score to update_data: {confidence_score}")
                    if conclusion is not None:
                        update_data["conclusion"] = conclusion
                        logger.info(f"[CONCLUSION DEBUG] Added conclusion to update_data: {conclusion[:50]}...")
                    
                    logger.info(f"[CONCLUSION DEBUG] Final update_data: {update_data}")
                    await self.prisma_service.prisma.transcription.update(
                        where={"id": transcription_row.id},
                        data=update_data
                    )
                    logger.info(f"Updated confidenceScore: {confidence_score} and conclusion: {conclusion[:50] if conclusion else 'None'}... for call {call_sid} in DB.")
            else:
                logger.warning(f"[CONCLUSION DEBUG] No updates to perform - confidence_score: {confidence_score}, conclusion: {conclusion}")
        except Exception as e:
            logger.error(f"Error saving single JSON transcription to database for call {call_sid}: {e}")
            logger.error(f"Transcript data that failed: {transcript_json[:200]}...")
        if call_sid in GLOBAL_LIVE_CONVERSATION_BUFFERS:
            del GLOBAL_LIVE_CONVERSATION_BUFFERS[call_sid]
            logger.info(f"Cleaned up global in-memory buffer for call {call_sid}")

    def cleanup_transcription_buffer(self, call_sid: str):
        # This method is now a redundant wrapper for the deletion in finalize_call_transcriptions
        # It's better to ensure finalize_call_transcriptions is always called.
        pass

    async def handle_media_stream(self, websocket, initial_call_sid: str = None):
        """Handle the media stream between Twilio and OpenAI."""
        logger.info(f"WebSocketService: handle_media_stream called with initial_call_sid: {initial_call_sid}")
        openai_ws = None
        effective_call_sid = initial_call_sid
        phone_number_for_context = None  # Initialize phone number for context early

        try:
            # We no longer need `async with self.redis_service:` here
            # as Redis connection is managed at app startup/shutdown
            
            openai_ws = await websockets.connect(
                'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
                extra_headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "OpenAI-Beta": "realtime=v1"
                }
            )
            logger.info("Connected to OpenAI WebSocket from WebSocketService")
            
            # --- NEW LOGIC START ---
            # Attempt to get phone number from initial call_sid if available
            if effective_call_sid:
                try:
                    async with self.prisma_service:
                        call_log_entry = await self.prisma_service.get_call_log(effective_call_sid)
                        if call_log_entry:
                            phone_number_for_context = call_log_entry.toNumber
                            logger.info(f"Extracted phone number from initial_call_sid: {phone_number_for_context}")
                except Exception as e:
                    logger.warning(f"Could not extract phone number from initial_call_sid: {e}")

            # Initialize OpenAI session with basic setup (no greeting yet)
            # We explicitly pass None for phone_number_for_context here because
            # we haven't received the Twilio 'start' event yet for incoming calls.
            # The context will be re-initialized once the 'start' event arrives.
            await self.initialize_session(openai_ws, effective_call_sid, phone_number_for_context)
            logger.info(f"[CONTEXT DEBUG] Initial initialize_session called with call_sid: {effective_call_sid}, phone_number: {phone_number_for_context}")
            
            # Don't send greeting yet - wait for Twilio start event to get proper context
            # --- NEW LOGIC END ---

            stream_sid = None
            latest_media_timestamp = 0
            last_assistant_item = None
            mark_queue = []
            response_start_timestamp_twilio = None
            current_session_id = None 

            async def receive_from_twilio_task():
                nonlocal stream_sid, latest_media_timestamp, effective_call_sid, phone_number_for_context
                call_context = None  # Local variable for this task
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        logger.debug(f"Received from Twilio: {data['event']}")
                        
                        # Refined logic for handling the 'start' event
                        if data.get('event') == 'start':
                            logger.info(f"[CONTEXT DEBUG] Received Twilio start event: {data}")
                            new_call_sid = data['start'].get('callSid')
                            
                            # Correctly extract phone number from 'customParameters'
                            phone_number_from_start = None
                            if 'customParameters' in data['start']:
                                logger.info(f"[CONTEXT DEBUG] Start event customParameters: {data['start']['customParameters']}")
                                phone_number_from_start = data['start']['customParameters'].get('From')
                                if not phone_number_from_start:  # Fallback to 'To' if 'From' is not present
                                    phone_number_from_start = data['start']['customParameters'].get('To')
                                
                                if phone_number_from_start:
                                    phone_number_for_context = phone_number_from_start
                                    logger.info(f"[CONTEXT DEBUG] Extracted and set phone_number_for_context from customParameters: {phone_number_for_context}")
                            else:
                                logger.warning(f"[CONTEXT DEBUG] No 'customParameters' found in start event: {data['start']}")
                            
                            # Update call_sid if we got a new one
                            if new_call_sid and new_call_sid != effective_call_sid:
                                logger.info(f"receive_from_twilio_task: UPDATED effective_call_sid from Twilio start event: {new_call_sid}")
                                effective_call_sid = new_call_sid
                            
                            # Always re-initialize session with proper call_sid and updated phone number
                            logger.info(f"[CONTEXT DEBUG] About to re-initialize session with call_sid: {effective_call_sid}, phone_number: {phone_number_for_context}")
                            call_context = await self.initialize_session(openai_ws, effective_call_sid, phone_number_for_context)
                            
                            # Now extract context and send the context-aware greeting
                            context = None
                            if call_context and call_context.get('call_history'):
                                context = self.context_service.extract_context_from_call_history(call_context['call_history'])
                            
                            # Send the initial greeting with proper context
                            if openai_ws and openai_ws.open:
                                await self.trigger_initial_conversation(openai_ws, context)
                                logger.info("Triggered context-aware initial conversation after getting Twilio start event")
                                
                            stream_sid = data['start']['streamSid']
                            logger.info(f"Incoming stream has started {stream_sid} for call_sid: {effective_call_sid}")
                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None

                        elif data['event'] == 'media' and openai_ws.open:
                            latest_media_timestamp = int(data['media']['timestamp'])
                            audio_append = {
                                "type": "input_audio_buffer.append",
                                "audio": data['media']['payload']
                            }
                            await openai_ws.send(json.dumps(audio_append))
                            logger.debug("Sent audio chunk to OpenAI")

                        elif data['event'] == 'mark':
                            if mark_queue:
                                mark_queue.pop(0)
                                logger.debug("Processed mark event")
                except websockets.exceptions.ConnectionClosedOK:
                    logger.info("Twilio WebSocket connection closed normally.")
                except Exception as e:
                    logger.error(f"Error in receive_from_twilio for call_sid {effective_call_sid}: {str(e)}")
                    if "Foreign key constraint failed" in str(e) or "database" in str(e).lower():
                        logger.warning(f"Database error in receive_from_twilio, continuing: {str(e)}")
                    else:
                        if openai_ws and openai_ws.open:
                            await openai_ws.close()

            async def send_to_twilio_task():
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, current_session_id, effective_call_sid
                try:
                    async for openai_message in openai_ws:
                        response = json.loads(openai_message)
                        
                        if response['type'] in LOG_EVENT_TYPES:
                            logger.info(f"Received OpenAI event: {response['type']} for call_sid: {effective_call_sid}")
                        
                        if effective_call_sid:
                            await self.process_openai_message(effective_call_sid, response, current_session_id)
                        else:
                            logger.warning(f"send_to_twilio_task: effective_call_sid is None, cannot process OpenAI message for transcription.")
                        
                        if response.get('type') == 'session.created':
                            current_session_id = response.get('session', {}).get('id')
                            logger.info(f"Session created with ID: {current_session_id} for call_sid: {effective_call_sid}")
                        
                        if response.get('type') == 'response.audio.delta' and 'delta' in response:
                            # Add small delay to control speech rate and prevent rapid audio streaming
                            await asyncio.sleep(0.02)  # 20ms delay between audio chunks for natural pacing
                            
                            audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                            audio_delta = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
                                }
                            }
                            await websocket.send_json(audio_delta)
                            logger.debug(f"Sent audio response to Twilio for call_sid: {effective_call_sid}")
                            
                            if response_start_timestamp_twilio is None:
                                response_start_timestamp_twilio = latest_media_timestamp
                            
                            if response.get('item_id'):
                                last_assistant_item = response['item_id']
                            
                            await self.send_mark(websocket, stream_sid, mark_queue)
                        
                        if response.get('type') == 'input_audio_buffer.speech_started':
                            logger.info(f"🎤 Speech started detected for call_sid: {effective_call_sid}")
                            # Handle interruption immediately when user starts speaking
                            await self.handle_speech_started_event(
                                openai_ws, websocket, stream_sid,
                                response_start_timestamp_twilio,
                                last_assistant_item,
                                latest_media_timestamp,
                                mark_queue
                            )
                            # Reset tracking variables after handling interruption
                            last_assistant_item = None
                            response_start_timestamp_twilio = None
                        
                        if response.get('type') == 'input_audio_buffer.speech_stopped':
                            logger.info(f"🛑 Speech stopped detected for call_sid: {effective_call_sid}")
                        
                        if response.get('type') == 'session.ended':
                            if current_session_id:
                                async with self.prisma_service:
                                    await self.prisma_service.update_session_status(current_session_id, "completed")
                            
                            if effective_call_sid:
                                self.transcription_service.end_call_transcription(effective_call_sid)
                            
                            logger.info(f"Session ended for call_sid: {effective_call_sid}")
                            
                except websockets.exceptions.ConnectionClosedOK:
                    logger.info(f"OpenAI WebSocket connection closed normally for call_sid: {effective_call_sid}.")
                except Exception as e:
                    logger.error(f"Error in send_to_twilio for call_sid {effective_call_sid}: {str(e)}")

            # Start both tasks concurrently
            await asyncio.gather(receive_from_twilio_task(), send_to_twilio_task())
            
        except websockets.exceptions.ConnectionClosedOK:
            logger.info(f"Twilio WebSocket connection closed normally or OpenAI closed for call_sid: {effective_call_sid}.")
        except Exception as e:
            logger.error(f"Error in outer media stream handler for call_sid {effective_call_sid}: {str(e)}")
            raise
        finally:
            if effective_call_sid:
                logger.info(f"Final cleanup for call_sid: {effective_call_sid}")
                self.transcription_service.end_call_transcription(effective_call_sid)
                await self.finalize_call_transcriptions(effective_call_sid)
                logger.info(f"Finalized transcription tracking for call {effective_call_sid} due to connection close")
            else:
                logger.warning("No effective_call_sid available in finally block for media stream cleanup.")
            
            if openai_ws and openai_ws.open:
                await openai_ws.close()