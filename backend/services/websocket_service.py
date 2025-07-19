import json
import base64
import asyncio
import websockets
import logging
from config import OPENAI_API_KEY
from services.prisma_service import PrismaService
from services.transcription_service import TranscriptionService, SpeakerType
from typing import List, Dict, Any
from datetime import datetime
from services.redis_service import RedisService

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
        logger.debug(f"TranscriptionBuffer created for call_sid: {call_sid}")
    
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
        logger.debug(f"Added to buffer - {speaker}: {text[:50]}...")
    
    def set_session_info(self, session_id: str, call_log_id: int):
        """Set session and call log information"""
        self.session_id = session_id
        self.call_log_id = call_log_id
    
    async def flush_to_database(self, prisma_service: PrismaService):
        """Save all buffered transcriptions to the database"""
        logger.debug(f"[flush_to_database] call_log_id: {self.call_log_id}, session_id: {self.session_id}, num_transcriptions: {len(self.transcriptions)}")
        if not self.transcriptions or not self.call_log_id:
            logger.warning(f"No transcriptions to save or missing call_log_id for call {self.call_sid}")
            logger.debug(f"[flush_to_database] Buffer contents: {self.transcriptions}")
            return
        
        try:
            async with prisma_service:
                saved_count = 0
                for transcription in self.transcriptions:
                    try:
                        await prisma_service.add_transcription(
                            call_log_id=self.call_log_id,
                            speaker=transcription['speaker'],
                            text=transcription['text'],
                            confidence=transcription['confidence'],
                            session_id=self.session_id,
                            is_final=transcription['is_final']
                        )
                        saved_count += 1
                    except Exception as e:
                        logger.error(f"Error saving individual transcription: {str(e)}")
                        logger.debug(f"Failed transcription data: {transcription}")
                
                logger.info(f"Successfully saved {saved_count}/{len(self.transcriptions)} transcriptions for call {self.call_sid}")
                
        except Exception as e:
            logger.error(f"Error flushing transcriptions to database for call {self.call_sid}: {str(e)}")
            logger.debug(f"[flush_to_database] Buffer contents: {self.transcriptions}")
    
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
        self.transcription_service = TranscriptionService()
        self.prisma_service = PrismaService()
        self.redis_service = RedisService()
        self.live_transcription_buffers = {}  # call_sid -> list of {speaker, text}
        logger.info(f"WebSocketService initialized (ID: {id(self)}) with transcription service and Redis buffer")

    def get_transcription_service(self):
        """Get the transcription service instance."""
        return self.transcription_service

    def _get_redis_transcription_key(self, call_sid: str) -> str:
        return f"transcription:{call_sid}"

    def _get_redis_session_key(self, call_sid: str) -> str:
        return f"transcription_session:{call_sid}"

    async def _buffer_transcription(self, call_sid: str, speaker: str, text: str):
        logger.info(f"[Buffer] _buffer_transcription called (Redis): call_sid={call_sid}, speaker={speaker}, text={text[:50]}...")
        if not call_sid:
            logger.warning(f"[Buffer] No call_sid provided, skipping Redis buffering for speaker={speaker}, text={text[:50]}...")
            return

        entry = {
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "is_final": True
        }
        
        try:
            # IMPORTANT: Ensure Redis is connected before using its methods
            # This is handled by the `async with self.redis_service` block in handle_media_stream,
            # but for a standalone method like this, it's safer to ensure it here if not using __aenter__ around it.
            # However, since this method is called within handle_media_stream's context,
            # we can rely on the parent context for connection.
            if self.redis_service.client is None:  # Double check if client is set up
                logger.error(f"Redis client is None in _buffer_transcription for call {call_sid}. Falling back to in-memory.")
                raise ConnectionError("Redis client not initialized or connected.")

            await self.redis_service.client.rpush(self._get_redis_transcription_key(call_sid), json.dumps(entry))
            logger.debug(f"[Buffer] Appended transcription to Redis list for call_sid={call_sid}. Current list length: {await self.redis_service.client.llen(self._get_redis_transcription_key(call_sid))}")
        except Exception as e:
            logger.error(f"Error buffering transcription to Redis for call {call_sid}: {e}")
            # Fallback to in-memory buffer if Redis fails
            if call_sid not in self.live_transcription_buffers:
                self.live_transcription_buffers[call_sid] = []
            self.live_transcription_buffers[call_sid].append({
                "speaker": speaker,
                "text": text,
                "timestamp": datetime.now(),
                "is_final": True
            })

    async def initialize_session(self, openai_ws, call_sid: str = None):
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
        await openai_ws.send(json.dumps(session_update))
        
        # Create session in database and start transcription if call_sid is provided
        if call_sid:
            try:
                async with self.prisma_service:
                    # Start transcription tracking
                    self.transcription_service.start_call_transcription(call_sid)
                    logger.info(f"Started transcription tracking for call {call_sid}")
                    
                    # Get the call log to get its ID
                    call_log = await self.prisma_service.get_call_log(call_sid)
                    if call_log:
                        # Create a session ID
                        session_id = f"session_{call_sid}"
                        session = await self.prisma_service.create_session(
                            session_id=session_id,
                            model="gpt-4o-realtime-preview-2024-10-01",
                            voice=VOICE
                        )
                        # Link session to call using the actual session.id, not session_id
                        await self.prisma_service.link_session_to_call(session.id, call_sid)
                        await self.prisma_service.update_session_status(session_id, "active")
                        
                        # Store session info in Redis
                        await self.redis_service.client.hset(self._get_redis_session_key(call_sid), mapping={
                            "session_id": session_id,
                            "call_log_id": call_log.id
                        })
                        logger.info(f"Redis session metadata set for call {call_sid}")
            except Exception as db_error:
                logger.warning(f"Database error during session initialization for call {call_sid}: {str(db_error)}")
                logger.warning("Continuing with call without database session tracking")
        
        # Send initial greeting
        initial_conversation_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Greet the business owner with 'Hello! I'm calling from Teya UK, a leading provider of smart payment solutions for modern businesses. I'd love to learn more about your business and see how we might be able to help you with your payment processing needs. Could you tell me a bit about your business?'"
                    }
                ]
            }
        }
        await openai_ws.send(json.dumps(initial_conversation_item))
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
        logger.info(f"[OpenAI] Received event type: {message.get('type')}, message: {message.get('transcript')[:50] if message.get('transcript') else 'N/A'}")
        
        # Call the transcription_service first, as it maintains active_transcriptions
        self.transcription_service.process_openai_message(call_sid, message)

        # Buffer parts to Redis for persistence
        if call_sid:
            message_type = message.get("type")
            if message_type in ["response.audio_transcript.delta", "response.audio_transcript.done"]:
                transcript = message.get("transcript", "")
                if transcript:
                    await self._buffer_transcription(call_sid, "assistant", transcript)  # AWAIT this call
            elif message_type in ["conversation.item.input_audio_transcription.delta", "conversation.item.input_audio_transcription.completed"]:
                transcript = message.get("transcript", "")
                if transcript:
                    await self._buffer_transcription(call_sid, "user", transcript)  # AWAIT this call
        else:
            logger.error(f"process_openai_message: received message with no call_sid. Message type: {message.get('type')}")

    async def finalize_call_transcriptions(self, call_sid: str):
        """Save all buffered transcriptions from Redis to database when call ends"""
        logger.info(f"Attempting to finalize transcriptions for call {call_sid} (WS Service ID: {id(self)})")
        
        # Ensure Redis client is available before using it
        if self.redis_service.client is None:
            logger.warning(f"Redis client not available in finalize_call_transcriptions for {call_sid}. Attempting fallback to in-memory buffer.")
            raw_transcription_entries_json = []  # No Redis data
        else:
            try:
                raw_transcription_entries_json = await self.redis_service.client.lrange(self._get_redis_transcription_key(call_sid), 0, -1)
            except Exception as e:
                logger.error(f"Error retrieving Redis data for finalization of call {call_sid}: {e}. Falling back to in-memory.")
                raw_transcription_entries_json = []  # Clear Redis data if fetch fails

        if not raw_transcription_entries_json:
            logger.warning(f"No buffered transcription data found in Redis for call {call_sid}")
            # Fallback to in-memory buffer if Redis failed or had no data
            buffer = self.live_transcription_buffers.get(call_sid)
            if buffer:
                logger.info(f"Using fallback in-memory buffer for call {call_sid} with {len(buffer)} entries")
                buffered_transcriptions = [entry for entry in buffer]  # No need to json.dumps if already dicts
            else:
                logger.warning(f"No transcription data found in Redis or memory for call {call_sid}")
                return  # No data to save
        else:
            buffered_transcriptions = [json.loads(entry) for entry in raw_transcription_entries_json]  # Parse only if from Redis
        
        # Get call_log_id and session_id from Redis metadata or fallback to Prisma
        session_meta = {}
        if self.redis_service.client:
            try:
                session_meta = await self.redis_service.client.hgetall(self._get_redis_session_key(call_sid))
            except Exception as e:
                logger.error(f"Error retrieving Redis session metadata for call {call_sid}: {e}")

        call_log_id = int(session_meta.get("call_log_id")) if session_meta.get("call_log_id") else None
        session_id_from_redis = session_meta.get("session_id")

        if not call_log_id:
            logger.error(f"Cannot finalize transcriptions: No call_log_id found in Redis metadata for call {call_sid}. Trying Prisma fallback.")
            try:
                call_log_fallback = await self.prisma_service.get_call_log(call_sid)  # Use get_call_log, not get_call_log_by_sid
                if call_log_fallback:
                    call_log_id = call_log_fallback.id
                    logger.info(f"Fallback: Retrieved call_log_id {call_log_id} from Prisma for call {call_sid}")
                else:
                    logger.error(f"Prisma fallback also failed to find call log for {call_sid}. Cannot save transcriptions.")
                    return  # Critical failure: cannot save without call_log_id
            except Exception as e:
                logger.error(f"Fallback to Prisma for call_log_id failed for {call_sid}: {e}")
                return  # Cannot save without call_log_id

        transcription_data_for_db = []
        for entry in buffered_transcriptions:
            # Ensure timestamp is a datetime object
            timestamp_obj = entry.get("timestamp")
            if isinstance(timestamp_obj, str):
                try:
                    timestamp_obj = datetime.fromisoformat(timestamp_obj)
                except ValueError:
                    logger.warning(f"Invalid timestamp format in Redis entry for call {call_sid}: {entry['timestamp']}. Using current time.")
                    timestamp_obj = datetime.now()
            elif not isinstance(timestamp_obj, datetime):
                timestamp_obj = datetime.now()  # Default to now if not string or datetime

            transcription_data_for_db.append({
                'call_log_id': call_log_id,
                'session_id': session_id_from_redis, 
                'speaker': entry["speaker"],
                'text': entry["text"],
                'confidence': entry.get("confidence"),
                'is_final': entry.get("is_final", True),
                'timestamp': timestamp_obj
            })

        try:
            async with self.prisma_service:
                result = await self.prisma_service.add_transcriptions_batch(transcription_data_for_db)
                logger.info(f"Successfully saved {result.count} transcriptions for call {call_sid} to DB via batch.")
        except Exception as e:
            logger.error(f"Error saving batch transcriptions to database for call {call_sid}: {e}")

        # Clean up Redis after successful save
        if self.redis_service.client:
            try:
                await self.redis_service.client.delete(self._get_redis_transcription_key(call_sid))
                await self.redis_service.client.delete(self._get_redis_session_key(call_sid))
                logger.info(f"Cleaned up Redis buffers for call {call_sid}")
            except Exception as e:
                logger.error(f"Error cleaning up Redis for call {call_sid}: {e}")

        # Always clean up in-memory buffer (it's a fallback)
        if call_sid in self.live_transcription_buffers:
            del self.live_transcription_buffers[call_sid]

    def cleanup_transcription_buffer(self, call_sid: str):
        # No-op for Redis, cleanup handled in finalize_call_transcriptions
        pass

    async def handle_media_stream(self, websocket, initial_call_sid: str = None):
        """Handle the media stream between Twilio and OpenAI."""
        logger.info(f"WebSocketService: handle_media_stream called with initial_call_sid: {initial_call_sid}")
        openai_ws = None
        
        # This will be the definitive call_sid used throughout this WebSocket's lifetime
        effective_call_sid = initial_call_sid

        try:
            # The async with self.redis_service will ensure connection for this context
            async with self.redis_service:  # This ensures _client is connected and available
                openai_ws = await websockets.connect(
                    'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
                    extra_headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "OpenAI-Beta": "realtime=v1"
                    }
                )
                logger.info("Connected to OpenAI WebSocket from WebSocketService")
                
                # Use the initial_call_sid for session initialization
                await self.initialize_session(openai_ws, effective_call_sid)

                # Connection specific state. These are local, so no need for _ prefixes unless
                # they are modified by nonlocal scope inside nested functions.
                stream_sid = None
                latest_media_timestamp = 0
                last_assistant_item = None
                mark_queue = []
                response_start_timestamp_twilio = None
                current_session_id = None  # This will be set by session.created event

                async def receive_from_twilio_task():
                    nonlocal stream_sid, latest_media_timestamp, effective_call_sid
                    try:
                        async for message in websocket.iter_text():
                            data = json.loads(message)
                            logger.debug(f"Received from Twilio: {data['event']}")
                            
                            # Crucial: If effective_call_sid is None, try to get it from the 'start' event
                            if effective_call_sid is None and data.get('event') == 'start':
                                if 'start' in data and 'callSid' in data['start']:
                                    effective_call_sid = data['start']['callSid']
                                    logger.info(f"UPDATED effective_call_sid from Twilio start event: {effective_call_sid}")
                                elif 'start' in data and 'parameters' in data['start'] and 'CallSid' in data['start']['parameters']:
                                    effective_call_sid = data['start']['parameters']['CallSid']
                                    logger.info(f"UPDATED effective_call_sid from Twilio stream parameters: {effective_call_sid}")
                                # Also, re-initialize the OpenAI session with the newly found call_sid
                                # This handles cases where the initial call_sid was missing from query params
                                if effective_call_sid and effective_call_sid != initial_call_sid:
                                    await self.initialize_session(openai_ws, effective_call_sid)
                            
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
                        # Don't close the connection on database errors, just log them
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
                            
                            if effective_call_sid:  # Use the established effective_call_sid
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