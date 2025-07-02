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
        logger.debug(f"Added to buffer - {speaker}: {text[:50]}...")
    
    def set_session_info(self, session_id: str, call_log_id: int):
        """Set session and call log information"""
        self.session_id = session_id
        self.call_log_id = call_log_id
    
    async def flush_to_database(self, prisma_service: PrismaService):
        """Save all buffered transcriptions to the database"""
        if not self.transcriptions or not self.call_log_id:
            logger.warning(f"No transcriptions to save or missing call_log_id for call {self.call_sid}")
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
                
                logger.info(f"Successfully saved {saved_count}/{len(self.transcriptions)} transcriptions for call {self.call_sid}")
                
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
        self.transcription_service = TranscriptionService()
        self.prisma_service = PrismaService()
        # Dictionary to store transcription buffers by call_sid
        self.transcription_buffers: Dict[str, TranscriptionBuffer] = {}
        logger.info("WebSocketService initialized with transcription service")

    def get_transcription_service(self):
        """Get the transcription service instance."""
        return self.transcription_service

    def get_or_create_transcription_buffer(self, call_sid: str) -> TranscriptionBuffer:
        """Get or create a transcription buffer for a call"""
        if call_sid not in self.transcription_buffers:
            self.transcription_buffers[call_sid] = TranscriptionBuffer(call_sid)
            logger.info(f"Created transcription buffer for call {call_sid}")
        return self.transcription_buffers[call_sid]

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
                    # Link session to call
                    await self.prisma_service.link_session_to_call(session_id, call_sid)
                    await self.prisma_service.update_session_status(session_id, "active")
                    
                    # Set session info in transcription buffer
                    buffer = self.get_or_create_transcription_buffer(call_sid)
                    buffer.set_session_info(session_id, call_log.id)
        
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
        """Process OpenAI WebSocket message and add to transcription buffer."""
        try:
            # Use the transcription service to process the message
            self.transcription_service.process_openai_message(call_sid, message)
            
            # Add to transcription buffer
            if call_sid:
                buffer = self.get_or_create_transcription_buffer(call_sid)
                message_type = message.get("type")
                
                # Handle completed user transcriptions
                if message_type == "conversation.item.input_audio_transcription.completed":
                    transcript = message.get("transcript", "")
                    if transcript:
                        buffer.add_transcription(
                            speaker="user",
                            text=transcript
                        )
                
                # Handle assistant audio transcriptions
                elif message_type == "response.audio_transcript.done":
                    transcript = message.get("transcript", "")
                    if transcript:
                        buffer.add_transcription(
                            speaker="assistant",
                            text=transcript
                        )
                
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
                
        except Exception as e:
            logger.error(f"Error processing OpenAI message for transcription: {str(e)}")

    async def finalize_call_transcriptions(self, call_sid: str):
        """Save all buffered transcriptions to database when call ends"""
        if call_sid in self.transcription_buffers:
            buffer = self.transcription_buffers[call_sid]
            
            logger.info(f"Finalizing transcriptions for call {call_sid}. Buffer contains {buffer.get_transcription_count()} transcriptions")
            
            # Save to database
            await buffer.flush_to_database(self.prisma_service)
            
            # Log the full conversation for debugging
            if buffer.get_transcription_count() > 0:
                logger.info(f"Full conversation for call {call_sid}:\n{buffer.get_full_conversation()}")
            
            # Clean up the buffer
            del self.transcription_buffers[call_sid]
            logger.info(f"Cleaned up transcription buffer for call {call_sid}")
        else:
            logger.warning(f"No transcription buffer found for call {call_sid}")

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
                        
                        # Log important events
                        if response['type'] in LOG_EVENT_TYPES:
                            logger.info(f"Received OpenAI event: {response['type']}")
                        
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
                        
                        # Handle session creation
                        if response.get('type') == 'session.created':
                            current_session_id = response.get('session', {}).get('id')
                            logger.info(f"Session created with ID: {current_session_id}")
                        
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
                                    await self.prisma_service.update_session_status(current_session_id, "completed")
                            
                            # End transcription tracking
                            if call_sid:
                                self.transcription_service.end_call_transcription(call_sid)
                            
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
                self.transcription_service.end_call_transcription(call_sid)
                await self.finalize_call_transcriptions(call_sid)
                logger.info(f"Finalized transcription tracking for call {call_sid} due to connection close")