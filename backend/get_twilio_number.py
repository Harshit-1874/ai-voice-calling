import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TWILIO_PHONE_NUMBER

print(f"Twilio Phone Number: {TWILIO_PHONE_NUMBER}")
print(f"Call this number and speak clearly for 3-5 seconds to test transcription")
print(f"The server is running and monitoring logs are active")
