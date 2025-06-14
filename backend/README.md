# AI Voice Calling Backend

This is the backend service for the AI Voice Calling system, built with FastAPI and Python.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the backend directory with the following variables:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number

# HubSpot Configuration
HUBSPOT_API_KEY=your_hubspot_api_key

# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/voice_calling_db

# Server Configuration
PORT=8000
HOST=0.0.0.0
DEBUG=True
```

4. Run the server:
```bash
uvicorn main:app --reload
```

## Project Structure

```
backend/
├── main.py              # FastAPI application entry point
├── requirements.txt     # Python dependencies
├── services/           # Service modules
│   ├── twilio_service.py    # Twilio integration
│   ├── openai_service.py    # OpenAI integration
│   ├── crm_service.py       # HubSpot CRM integration
│   └── db_service.py        # MongoDB database service
└── README.md           # This file
```

## API Endpoints

- `GET /`: Health check endpoint
- `GET /health`: Detailed health status
- `WebSocket /ws/{client_id}`: WebSocket endpoint for real-time voice communication

## Services

### Twilio Service
Handles all telephony operations including:
- Making outbound calls
- Receiving inbound calls
- Generating TwiML responses
- Managing call status

### OpenAI Service
Manages real-time voice communication:
- Creating realtime sessions
- Processing audio streams
- Managing voice responses
- Session management

### CRM Service
Handles HubSpot integration:
- Contact management
- Conversation logging
- Lead qualification
- Data synchronization

### Database Service
Manages data persistence:
- Conversation logging
- User data storage
- Call history
- Metadata management

## Development

To run the server in development mode with auto-reload:
```bash
uvicorn main:app --reload --port 8000
```

## Testing

To run tests:
```bash
pytest
```

## API Documentation

Once the server is running, you can access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc 