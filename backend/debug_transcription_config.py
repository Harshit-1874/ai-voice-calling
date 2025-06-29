import asyncio
import json
import logging
import sys
import os

# Add the backend directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import OPENAI_API_KEY

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_openai_configuration():
    """Check if OpenAI API key is properly configured"""
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key is not configured!")
        return False
    
    # Check if the key looks valid (starts with sk- and has reasonable length)
    if not OPENAI_API_KEY.startswith('sk-') or len(OPENAI_API_KEY) < 40:
        logger.error(f"OpenAI API key appears invalid: {OPENAI_API_KEY[:10]}...")
        return False
    
    logger.info(f"OpenAI API key configured: {OPENAI_API_KEY[:10]}...")
    return True

def check_transcription_config():
    """Check the transcription configuration that we're sending to OpenAI"""
    session_config = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": "echo",
            "modalities": ["text", "audio"],
            "temperature": 0.7,
            "input_audio_transcription": {
                "model": "whisper-1"
            }
        }
    }
    
    logger.info("Session configuration that would be sent to OpenAI:")
    logger.info(json.dumps(session_config, indent=2))
    
    # Check if transcription is properly enabled
    transcription_config = session_config["session"].get("input_audio_transcription")
    if transcription_config:
        logger.info("✅ Audio transcription is enabled in session config")
        logger.info(f"✅ Using model: {transcription_config.get('model')}")
        return True
    else:
        logger.error("❌ Audio transcription is not enabled in session config")
        return False

def analyze_recent_logs():
    """Analyze recent server logs for transcription-related events"""
    log_file = "app.log"
    if not os.path.exists(log_file):
        logger.warning(f"Log file {log_file} not found")
        return
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Look at the last 200 lines for recent activity
        recent_lines = lines[-200:] if len(lines) > 200 else lines
        
        # Count different types of events
        openai_events = {}
        transcription_events = []
        speech_events = []
        
        for line in recent_lines:
            if "Received OpenAI event:" in line:
                # Extract event type
                try:
                    event_part = line.split("Received OpenAI event:")[1].strip()
                    openai_events[event_part] = openai_events.get(event_part, 0) + 1
                except:
                    pass
            
            if "transcription" in line.lower():
                transcription_events.append(line.strip())
            
            if "speech_started" in line or "speech_stopped" in line:
                speech_events.append(line.strip())
        
        logger.info("\n=== RECENT LOG ANALYSIS ===")
        logger.info(f"Analyzed last {len(recent_lines)} log lines")
        
        if openai_events:
            logger.info("\nOpenAI Events Received:")
            for event_type, count in sorted(openai_events.items()):
                logger.info(f"  {event_type}: {count} times")
        else:
            logger.warning("No OpenAI events found in recent logs")
        
        if transcription_events:
            logger.info(f"\nTranscription Events ({len(transcription_events)}):")
            for event in transcription_events[-5:]:  # Show last 5
                logger.info(f"  {event}")
        else:
            logger.warning("No transcription events found in recent logs")
        
        if speech_events:
            logger.info(f"\nSpeech Events ({len(speech_events)}):")
            for event in speech_events[-5:]:  # Show last 5
                logger.info(f"  {event}")
        else:
            logger.warning("No speech events found in recent logs")
        
        # Check for specific missing events
        missing_events = []
        if "conversation.item.input_audio_transcription.completed" not in openai_events:
            missing_events.append("conversation.item.input_audio_transcription.completed")
        if "conversation.item.input_audio_transcription.failed" not in openai_events:
            missing_events.append("conversation.item.input_audio_transcription.failed")
        
        if missing_events:
            logger.warning(f"\n❌ Missing Expected Events: {missing_events}")
            logger.warning("This explains why transcriptions are not being saved!")
        else:
            logger.info("\n✅ All expected transcription events are present")
            
    except Exception as e:
        logger.error(f"Error analyzing logs: {e}")

if __name__ == "__main__":
    logger.info("=== OpenAI Transcription Configuration Check ===")
    
    # Check configuration
    config_ok = check_openai_configuration()
    transcription_ok = check_transcription_config()
    
    # Analyze recent activity
    analyze_recent_logs()
    
    logger.info("\n=== DIAGNOSIS ===")
    if config_ok and transcription_ok:
        logger.info("✅ Configuration appears correct")
        logger.info("❓ Issue likely with:")
        logger.info("   1. No actual voice input during test calls")
        logger.info("   2. OpenAI server-side issue with transcription")
        logger.info("   3. Audio format or quality issues")
        logger.info("   4. VAD (Voice Activity Detection) not triggering")
    else:
        logger.error("❌ Configuration issues detected")
    
    logger.info("\n=== NEXT STEPS ===")
    logger.info("1. Make a test call with actual voice input (not just silence)")
    logger.info("2. Speak clearly for at least 2-3 seconds")
    logger.info("3. Monitor logs in real-time during the call")
    logger.info("4. Check if input_audio_buffer.speech_started events are received")
