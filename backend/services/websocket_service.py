import json
import base64
import asyncio
import websockets
import logging
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

# OpenAI Configuration
VOICE = 'alloy'
SYSTEM_MESSAGE = (
    "You are a helpful and friendly AI assistant who loves to chat. "
    "You have a natural conversation style and are prepared to help with any topic. "
    "Always stay positive and engaging in your responses."
)
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created'
]

class WebSocketService:
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key not found in environment variables")
        self.api_key = OPENAI_API_KEY
        logger.info("WebSocketService initialized")

    async def initialize_session(self, openai_ws):
        """Initialize the OpenAI session with configuration."""
        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": VOICE,
                "instructions": SYSTEM_MESSAGE,
                "modalities": ["text", "audio"],
                "temperature": 0.8,
            }
        }
        logger.info('Sending session update')
        await openai_ws.send(json.dumps(session_update))
        
        # Send initial greeting
        initial_conversation_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Greet the user with 'Hello! I am an AI voice assistant. How can I help you today?'"
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

    async def handle_media_stream(self, websocket, openai_ws):
        """Handle the media stream between Twilio and OpenAI."""
        try:
            # Connection specific state
            stream_sid = None
            latest_media_timestamp = 0
            last_assistant_item = None
            mark_queue = []
            response_start_timestamp_twilio = None

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
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
                try:
                    async for openai_message in openai_ws:
                        response = json.loads(openai_message)
                        if response['type'] in LOG_EVENT_TYPES:
                            logger.info(f"Received OpenAI event: {response['type']}")
                        
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
                        
                        if response.get('type') == 'input_audio_buffer.speech_started':
                            logger.info("Speech started detected")
                            if last_assistant_item:
                                await self.handle_speech_started_event(
                                    openai_ws, websocket, stream_sid,
                                    response_start_timestamp_twilio,
                                    last_assistant_item,
                                    latest_media_timestamp,
                                    mark_queue
                                )
                except Exception as e:
                    logger.error(f"Error in send_to_twilio: {str(e)}")

            await asyncio.gather(receive_from_twilio(), send_to_twilio())
            
        except Exception as e:
            logger.error(f"Error in media stream: {str(e)}")
            raise 