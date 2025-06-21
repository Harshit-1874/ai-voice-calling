import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "file:./voice_calling.db")

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Server Configuration
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Validate required environment variables
def validate_env():
    if not TWILIO_ACCOUNT_SID:
        raise ValueError("TWILIO_ACCOUNT_SID environment variable is not set")
    if not TWILIO_AUTH_TOKEN:
        raise ValueError("TWILIO_AUTH_TOKEN environment variable is not set")
    if not TWILIO_PHONE_NUMBER:
        raise ValueError("TWILIO_PHONE_NUMBER environment variable is not set")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set") 