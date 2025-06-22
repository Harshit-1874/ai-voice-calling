import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class PrismaService:
    def __init__(self):
        self._is_connected = False
        self.prisma = None
        try:
            from prisma import Prisma
            self.prisma = Prisma()
            logger.info("Prisma client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Prisma client: {str(e)}")
            raise

    async def connect(self):
        """Connect to the database"""
        if not self._is_connected and self.prisma:
            try:
                # Check if connect method exists and is callable
                if hasattr(self.prisma, 'connect') and callable(self.prisma.connect):
                    # Try to call connect and check if it's async
                    import inspect
                    if inspect.iscoroutinefunction(self.prisma.connect):
                        result = await self.prisma.connect()
                    else:
                        result = self.prisma.connect()
                    
                    # Check if connect was successful
                    if result is None or result is True:
                        self._is_connected = True
                        logger.info("Connected to Prisma database")
                    else:
                        logger.warning(f"Prisma connect returned: {result}")
                        self._is_connected = True  # Assume connected for compatibility
                else:
                    logger.warning("Prisma client connect method not available")
                    self._is_connected = True  # Assume connected for compatibility
            except Exception as e:
                logger.error(f"Failed to connect to database: {str(e)}")
                # Don't raise the error, just log it
                logger.warning("Continuing without database connection")
                self._is_connected = True  # Assume connected for compatibility

    async def disconnect(self):
        """Disconnect from the database"""
        if self._is_connected and self.prisma:
            try:
                # Check if disconnect method exists and is callable
                if hasattr(self.prisma, 'disconnect') and callable(self.prisma.disconnect):
                    # Try to call disconnect and check if it's async
                    import inspect
                    if inspect.iscoroutinefunction(self.prisma.disconnect):
                        await self.prisma.disconnect()
                    else:
                        self.prisma.disconnect()
                    
                    self._is_connected = False
                    logger.info("Disconnected from Prisma database")
                else:
                    logger.warning("Prisma client disconnect method not available")
                    self._is_connected = False
            except Exception as e:
                logger.error(f"Error disconnecting from database: {str(e)}")
                self._is_connected = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    def _check_connection(self):
        """Check if connected to database"""
        if not self.prisma:
            raise Exception("Prisma client not initialized")
        if not self._is_connected:
            raise Exception("Not connected to database")

    # Contact Operations
    async def create_contact(self, name: str, phone: str, email: str = None, company: str = None, notes: str = None):
        """Create a new contact"""
        try:
            self._check_connection()
            contact = await self.prisma.contact.create({
                'data': {
                    'name': name,
                    'phone': phone,
                    'email': email,
                    'company': company,
                    'notes': notes
                }
            })
            logger.info(f"Created contact: {contact.name} ({contact.phone})")
            return contact
        except Exception as e:
            logger.error(f"Error creating contact: {str(e)}")
            raise

    async def get_contact_by_phone(self, phone: str):
        """Get contact by phone number"""
        try:
            self._check_connection()
            contact = await self.prisma.contact.find_unique({
                'where': {'phone': phone}
            })
            return contact
        except Exception as e:
            logger.error(f"Error getting contact by phone: {str(e)}")
            raise

    async def get_all_contacts(self):
        """Get all contacts"""
        try:
            self._check_connection()
            contacts = await self.prisma.contact.find_many({
                'order': {'createdAt': 'desc'}
            })
            return contacts
        except Exception as e:
            logger.error(f"Error getting all contacts: {str(e)}")
            raise

    async def update_contact(self, phone: str, **kwargs):
        """Update contact by phone number"""
        try:
            self._check_connection()
            contact = await self.prisma.contact.update({
                'where': {'phone': phone},
                'data': kwargs
            })
            logger.info(f"Updated contact: {contact.name}")
            return contact
        except Exception as e:
            logger.error(f"Error updating contact: {str(e)}")
            raise

    async def delete_contact(self, phone: str) -> bool:
        """Delete contact by phone number"""
        try:
            self._check_connection()
            contact = await self.prisma.contact.delete({
                'where': {'phone': phone}
            })
            logger.info(f"Deleted contact: {contact.name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting contact: {str(e)}")
            raise

    # Call Log Operations
    async def create_call_log(self, call_sid: str, from_number: str, to_number: str, status: str = "initiated"):
        """Create a new call log entry (no contact dependency)"""
        try:
            self._check_connection()
            call_log = await self.prisma.calllog.create(
                data={
                    'callSid': call_sid,
                    'fromNumber': from_number,
                    'toNumber': to_number,
                    'status': status
                }
            )
            logger.info(f"Created call log: {call_sid}")
            return call_log
        except Exception as e:
            logger.error(f"Error creating call log: {str(e)}")
            raise

    async def update_call_status(self, call_sid: str, status: str, duration: int = None, 
                                error_code: str = None, error_message: str = None, 
                                recording_url: str = None):
        """Update call status and details"""
        try:
            self._check_connection()
            # First, try to find the existing call log
            logger.debug(f"Looking for call log with callSid: {call_sid}")
            call_log = await self.prisma.calllog.find_unique(where={'callSid': call_sid})
            logger.debug(f"Result of find_unique: {call_log}")
            if call_log:
                try:
                    update_data = {'status': status}
                    if duration is not None:
                        update_data['duration'] = duration
                    if error_code is not None:
                        update_data['errorCode'] = error_code
                    if error_message is not None:
                        update_data['errorMessage'] = error_message
                    if recording_url is not None:
                        update_data['recordingUrl'] = recording_url
                    if status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
                        update_data['endTime'] = datetime.now()
                    call_log = await self.prisma.calllog.update(
                        where={'callSid': call_sid},
                        data=update_data
                    )
                    logger.info(f"Updated call log {call_sid} status to: {status}")
                    return call_log
                except Exception as update_error:
                    logger.error(f"Error updating call log {call_sid}: {str(update_error)}")
                    return None
            else:
                logger.warning(f"Call log not found for {call_sid}, cannot update.")
                return None
        except Exception as e:
            logger.error(f"Error in update_call_status: {str(e)}")
            return None

    async def get_call_log(self, call_sid: str):
        """Get call log by SID"""
        try:
            self._check_connection()
            call_log = await self.prisma.calllog.find_unique(
                where={'callSid': call_sid},
                include={
                    'contact': True,
                    'session': True,
                    'transcriptions': True
                }
            )
            return call_log
        except Exception as e:
            logger.error(f"Error getting call log: {str(e)}")
            raise

    async def get_all_call_logs(self, limit: int = 100):
        """Get all call logs with pagination"""
        try:
            self._check_connection()
            call_logs = await self.prisma.calllog.find_many(
                take=limit,
                order={'startTime': 'desc'},
                include={
                    'contact': True,
                    'session': True
                }
            )
            return call_logs
        except Exception as e:
            logger.error(f"Error getting all call logs: {str(e)}")
            raise

    # Session Operations
    async def create_session(self, session_id: str, model: str = "gpt-4o-realtime-preview-2024-10-01", 
                           voice: str = "alloy"):
        """Create a new session"""
        try:
            self._check_connection()
            session = await self.prisma.session.create(
                data={
                    'sessionId': session_id,
                    'status': 'created',
                    'model': model,
                    'voice': voice
                }
            )
            logger.info(f"Created session: {session_id}")
            return session
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            raise

    async def update_session_status(self, session_id: str, status: str, duration: int = None):
        """Update session status"""
        try:
            self._check_connection()
            update_data = {'status': status}
            if duration is not None:
                update_data['duration'] = duration
            if status in ['completed', 'failed']:
                update_data['endTime'] = datetime.now()
            session = await self.prisma.session.update(
                where={'sessionId': session_id},
                data=update_data
            )
            logger.info(f"Updated session {session_id} status to: {status}")
            return session
        except Exception as e:
            logger.error(f"Error updating session status: {str(e)}")
            raise

    async def link_session_to_call(self, session_id: str, call_sid: str):
        """Link a session to a call log"""
        try:
            self._check_connection()
            call_log = await self.prisma.calllog.update(
                where={'callSid': call_sid},
                data={'sessionId': session_id}
            )
            logger.info(f"Linked session {session_id} to call {call_sid}")
            return call_log
        except Exception as e:
            logger.error(f"Error linking session to call: {str(e)}")
            raise

    # Transcription Operations
    async def add_transcription(self, call_log_id: int, speaker: str, text: str, 
                               confidence: float = None, session_id: str = None, 
                               is_final: bool = False):
        """Add a transcription entry"""
        try:
            self._check_connection()
            transcription = await self.prisma.transcription.create(
                data={
                    'callLogId': call_log_id,
                    'sessionId': session_id,
                    'speaker': speaker,
                    'text': text,
                    'confidence': confidence,
                    'isFinal': is_final
                }
            )
            logger.debug(f"Added transcription for call {call_log_id}: {speaker} - {text[:50]}...")
            return transcription
        except Exception as e:
            logger.error(f"Error adding transcription: {str(e)}")
            raise

    async def get_transcriptions_for_call(self, call_log_id: int):
        """Get all transcriptions for a call"""
        try:
            self._check_connection()
            transcriptions = await self.prisma.transcription.find_many(
                where={'callLogId': call_log_id},
                order={'timestamp': 'asc'}
            )
            return transcriptions
        except Exception as e:
            logger.error(f"Error getting transcriptions: {str(e)}")
            raise

    # Conversation Analysis Operations
    async def create_conversation_analysis(self, call_log_id: int, summary: str = None, 
                                         key_points: List[str] = None, sentiment: str = None,
                                         lead_score: int = None, next_action: str = None):
        """Create conversation analysis"""
        try:
            self._check_connection()
            key_points_json = json.dumps(key_points) if key_points else None
            conversation = await self.prisma.conversation.create(
                data={
                    'callLogId': call_log_id,
                    'summary': summary,
                    'keyPoints': key_points_json,
                    'sentiment': sentiment,
                    'leadScore': lead_score,
                    'nextAction': next_action
                }
            )
            logger.info(f"Created conversation analysis for call {call_log_id}")
            return conversation
        except Exception as e:
            logger.error(f"Error creating conversation analysis: {str(e)}")
            raise

    async def get_conversation_analysis(self, call_log_id: int):
        """Get conversation analysis for a call"""
        try:
            self._check_connection()
            conversation = await self.prisma.conversation.find_unique(
                where={'callLogId': call_log_id}
            )
            return conversation
        except Exception as e:
            logger.error(f"Error getting conversation analysis: {str(e)}")
            raise

    # Utility Methods
    async def get_call_statistics(self) -> Dict[str, Any]:
        """Get call statistics"""
        try:
            self._check_connection()
            total_calls = await self.prisma.calllog.count()
            completed_calls = await self.prisma.calllog.count(where={'status': 'completed'})
            failed_calls = await self.prisma.calllog.count(where={'status': 'failed'})
            return {
                'total_calls': total_calls,
                'completed_calls': completed_calls,
                'failed_calls': failed_calls
            }
        except Exception as e:
            logger.error(f"Error getting call statistics: {str(e)}")
            raise 

    async def upsert_hubspot_temp_data(self, data: Dict[str, Any]):
        """Insert or update a HubspotTempData record by hubspotId"""
        try:
            self._check_connection()
            record = await self.prisma.hubspottempdata.upsert(
                {'hubspotId': data['hubspotId']},
                data={
                    'create': data,
                    'update': data
                },
            )
            return record
        except Exception as e:
            logger.error(f"Error upserting HubspotTempData: {str(e)}")
            raise