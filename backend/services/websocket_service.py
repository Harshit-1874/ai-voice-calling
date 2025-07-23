import json
import base64
import asyncio
import websockets
import logging
from config import OPENAI_API_KEY
from services.prisma_service import PrismaService
from services.hubspot_service import HubspotService
from services.transcription_service import TranscriptionService, SpeakerType
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
    "You are a professional sales representative for Teya UK, a leading provider of smart payment solutions for modern businesses. "
    "You always speak first and open the conversation with a friendly, confident introduction.\n"
    "Never wait for the user to speak first.\n"
    "Never ask 'How may I help you today?' or any support-style questions.\n"
    "You are a sales agent, not a support agent.\n"
    "Your goal is to quickly introduce yourself, state the value of Teya UK, and ask a relevant, open-ended sales question.\n"
    "Example opening: 'Hi, this is Teya UK. We help businesses like yours accept payments easily and affordably. Can I ask what kind of business you run?'\n"
    "Keep your responses short, natural, and focused on sales discovery.\n"
    "Never act as a support agent.\n"
    "CONVERSATION STYLE:\n"
    "- Speak like a real person having a casual business conversation, not a robot.\n"
    "- Use a warm, friendly, and engaging tone.\n"
    "- Keep your responses short and natural (1-2 sentences).\n"
    "- Never ask more than one question at a time.\n"
    "- Pause and listen after each question or statement, don't rush to the next topic.\n"
    "- If the user is silent, wait a couple of seconds before gently prompting again.\n"
    "- If the user gives a short answer, ask a follow-up or show interest before moving on.\n"
    "- Never overload the user with too much information at once.\n"
    "- Avoid long monologues.\n"
    "- Make the conversation interactive and engaging.\n"
    "- React naturally to what they say and build on it immediately.\n"
    "- If interrupted, stop and listen.\n"
    "- Don't acknowledge every small response like 'yes', 'yeah', 'okay' - just continue naturally.\n"
    "- Don't say 'Thank you for your response' or similar formal acknowledgments.\n"
    "- If you don't understand, politely ask for clarification.\n"
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

    async def initialize_session(self, openai_ws, call_sid: str = None):
        """Initialize the OpenAI session with configuration."""
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
            temperature = float(temp_str.value) if temp_str is not None else 0.7
        except (ValueError, TypeError):
            # Handle cases where the stored value is not a valid number
            temperature = 0.7

        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad","threshold": 0.65},  # Raised threshold for better turn-taking
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": voice.value,
                "instructions": instructions.value,
                "modalities": ["text", "audio"],
                "temperature": temperature,
                "input_audio_transcription": {
                    "model": "whisper-1"
                }
            }
        }
        logger.info('Sending session update')
        await openai_ws.send(json.dumps(session_update))
        
        # Create session in database and start transcription if call_sid is provided
        if call_sid:
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
        # Send initial greeting as assistant (sales-focused)
        # The Twilio <Say> already does the opener, so the AI should start with a follow-up
        initial_conversation_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "input_text",
                        "text": "That's great! What kind of customers do you usually serve at your business?"
                    }
                ]
            }
        }
        await openai_ws.send(json.dumps(initial_conversation_item))
        # Do NOT send response.create immediately

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
            conclusion = ""
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
            if confidence_score is not None:
                async with self.prisma_service:
                    await self.prisma_service.prisma.transcription.update(
                        where={"id": transcription_row.id},
                        data={"confidenceScore": confidence_score}
                    )
                    logger.info(f"Updated confidenceScore for call {call_sid} in DB.")
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
            
            await self.initialize_session(openai_ws, effective_call_sid)

            stream_sid = None
            latest_media_timestamp = 0
            last_assistant_item = None
            mark_queue = []
            response_start_timestamp_twilio = None
            current_session_id = None 

            async def receive_from_twilio_task():
                nonlocal stream_sid, latest_media_timestamp, effective_call_sid
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        logger.debug(f"Received from Twilio: {data['event']}")
                        
                        if effective_call_sid is None and data.get('event') == 'start':
                            if 'start' in data and 'callSid' in data['start']:
                                new_call_sid = data['start']['callSid']
                                logger.info(f"receive_from_twilio_task: UPDATED effective_call_sid from Twilio start event: {new_call_sid}")
                                effective_call_sid = new_call_sid 
                                await self.initialize_session(openai_ws, effective_call_sid)  # Re-initialize with correct SID
                            elif 'start' in data and 'parameters' in data['start'] and 'CallSid' in data['start']['parameters']:
                                new_call_sid = data['start']['parameters']['CallSid']
                                logger.info(f"receive_from_twilio_task: UPDATED effective_call_sid from Twilio stream parameters: {new_call_sid}")
                                effective_call_sid = new_call_sid
                                await self.initialize_session(openai_ws, effective_call_sid)  # Re-initialize with correct SID
                            else:
                                logger.warning(f"receive_from_twilio_task: Call SID not found in start event for immediate update.")

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
                            logger.info(f"Incoming stream has started {stream_sid} for call_sid: {effective_call_sid}")
                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None
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
                            if last_assistant_item:
                                await self.handle_speech_started_event(
                                    openai_ws, websocket, stream_sid,
                                    response_start_timestamp_twilio,
                                    last_assistant_item,
                                    latest_media_timestamp,
                                    mark_queue
                                )
                        
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