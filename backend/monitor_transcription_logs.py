import asyncio
import json
import logging
import sys
import os
import time
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def tail_logs(filename="app.log", lines=10):
    """Follow log file and print new lines"""
    if not os.path.exists(filename):
        logger.error(f"Log file {filename} not found!")
        return
    
    logger.info(f"Following {filename} for real-time logs...")
    logger.info("=" * 80)
    
    # Start from the end of the file
    with open(filename, 'r') as f:
        # Go to end of file
        f.seek(0, 2)
        file_size = f.tell()
        
        # Show last few lines first
        f.seek(max(0, file_size - 2000))  # Read last ~2000 characters
        initial_lines = f.readlines()
        if initial_lines:
            logger.info("Last few log entries:")
            for line in initial_lines[-lines:]:
                print(line.strip())
        
        logger.info("=" * 80)
        logger.info("Waiting for new log entries...")
        logger.info("Make a test call now and speak into the phone...")
        logger.info("=" * 80)
        
        # Now follow new lines
        while True:
            try:
                line = f.readline()
                if line:
                    line = line.strip()
                    # Highlight important events
                    if any(keyword in line.lower() for keyword in ['openai event', 'transcription', 'speech', 'audio', 'conversation.item']):
                        print(f"🔥 {line}")
                    else:
                        print(line)
                else:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                logger.info("\nStopping log monitoring...")
                break
            except Exception as e:
                logger.error(f"Error reading log: {e}")
                break

def check_audio_events():
    """Check recent logs for audio-related events"""
    log_file = "app.log"
    if not os.path.exists(log_file):
        return
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    # Look for audio-related events in recent logs
    recent_lines = lines[-100:] if len(lines) > 100 else lines
    
    audio_events = []
    speech_events = []
    media_events = []
    
    for line in recent_lines:
        line_lower = line.lower()
        if 'audio' in line_lower:
            audio_events.append(line.strip())
        if 'speech' in line_lower:
            speech_events.append(line.strip())
        if 'media' in line_lower and ('chunk' in line_lower or 'payload' in line_lower):
            media_events.append(line.strip())
    
    print(f"\nAudio events ({len(audio_events)}):")
    for event in audio_events[-3:]:
        print(f"  {event}")
    
    print(f"\nSpeech events ({len(speech_events)}):")
    for event in speech_events[-3:]:
        print(f"  {event}")
    
    print(f"\nMedia events ({len(media_events)}):")
    for event in media_events[-3:]:
        print(f"  {event}")

if __name__ == "__main__":
    logger.info("=== Real-time Log Monitor for Transcription Debugging ===")
    logger.info("This script will monitor logs in real-time to help debug transcription issues.")
    logger.info("")
    logger.info("Instructions:")
    logger.info("1. Make sure the server is running (python main.py)")
    logger.info("2. Start this script")
    logger.info("3. Make a test call to your Twilio number")
    logger.info("4. SPEAK CLEARLY into the phone for at least 3-5 seconds")
    logger.info("5. Watch for audio/speech/transcription events in the logs")
    logger.info("")
    
    # Check recent audio events first
    logger.info("Checking recent audio events...")
    check_audio_events()
    
    # Start tailing logs
    try:
        tail_logs()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
