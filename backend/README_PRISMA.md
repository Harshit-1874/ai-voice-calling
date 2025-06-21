# AI Voice Calling Backend with Prisma & SQLite

This backend implements a comprehensive AI voice calling system using Prisma ORM with SQLite database to store call logs, transcriptions, sessions, and contacts.

## Features

- **Call Management**: Track all calls with detailed status updates
- **Transcription Storage**: Store real-time conversation transcriptions
- **Session Management**: Track OpenAI sessions for each call
- **Contact Management**: Full CRUD operations for contacts
- **Call Analytics**: Detailed call statistics and conversation analysis
- **Database Integration**: Prisma ORM with SQLite for reliable data storage

## Database Schema

The system uses the following Prisma models:

### Contact
- Basic contact information (name, phone, email, company, notes)
- Links to call logs for call history

### CallLog
- Call details (SID, numbers, status, duration, timestamps)
- Error tracking and recording URLs
- Links to contacts and sessions

### Session
- OpenAI session tracking (session ID, status, model, voice)
- Duration and status management

### Transcription
- Real-time conversation transcriptions
- Speaker identification (user/assistant)
- Confidence scores and timestamps

### Conversation
- Post-call analysis (summary, key points, sentiment)
- Lead scoring and next action tracking

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the backend directory:

```env
# Database Configuration
DATABASE_URL="file:./voice_calling.db"

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_phone_number_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Server Configuration
BASE_URL=http://localhost:8000
PORT=8000
HOST=0.0.0.0
DEBUG=True
```

### 3. Initialize Database

Run the database initialization script:

```bash
python init_db.py
```

This will:
- Create the `.env` file if it doesn't exist
- Install Prisma CLI
- Generate Prisma client
- Push the schema to the database
- Verify the setup

### 4. Start the Server

```bash
python main.py
```

The server will start on `http://localhost:8000`

## API Endpoints

### Call Management

- `POST /call/{phone_number}` - Initiate a call
- `GET/POST /incoming-call` - Handle incoming calls
- `POST /call-status` - Handle call status updates
- `GET /call-logs` - Get all call logs with pagination
- `GET /call-logs/{call_sid}` - Get detailed call information

### Contact Management

- `POST /contacts` - Create a new contact
- `GET /contacts` - Get all contacts
- `GET /contacts/{phone}` - Get contact by phone number
- `GET /contacts/{phone}/calls` - Get contact with call history
- `PUT /contacts/{phone}` - Update contact
- `DELETE /contacts/{phone}` - Delete contact

### WebSocket

- `WS /media-stream?call_sid={call_sid}` - Real-time media streaming

## Database Operations

### Call Logging

Every call is automatically logged with:
- Call SID from Twilio
- Phone numbers (from/to)
- Status updates throughout the call lifecycle
- Duration and error information
- Recording URLs when available

### Transcription Storage

Real-time transcriptions are stored as they occur:
- Speaker identification (user/assistant)
- Text content with timestamps
- Confidence scores
- Session linking

### Session Management

OpenAI sessions are tracked:
- Session creation and linking to calls
- Status updates (created, active, completed, failed)
- Model and voice configuration
- Duration tracking

## Usage Examples

### Making a Call

```bash
curl -X POST "http://localhost:8000/call/+1234567890"
```

### Creating a Contact

```bash
curl -X POST "http://localhost:8000/contacts" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "phone": "+1234567890",
    "email": "john@example.com",
    "company": "Example Corp"
  }'
```

### Getting Call Logs

```bash
curl "http://localhost:8000/call-logs?limit=10"
```

### Getting Call Details

```bash
curl "http://localhost:8000/call-logs/CA1234567890abcdef"
```

## Database Queries

### Get Call Statistics

```python
async with prisma_service:
    stats = await prisma_service.get_call_statistics()
    print(f"Total calls: {stats['total_calls']}")
    print(f"Success rate: {stats['success_rate']}%")
```

### Get Contact with Call History

```python
async with prisma_service:
    contact = await prisma_service.get_contact_by_phone("+1234567890")
    if contact:
        call_logs = await prisma_service.prisma.calllog.find_many({
            'where': {'contactId': contact.id},
            'include': {'transcriptions': True}
        })
```

## Error Handling

The system includes comprehensive error handling:
- Database connection errors
- Twilio API errors
- OpenAI API errors
- Validation errors for phone numbers and data
- Proper HTTP status codes and error messages

## Logging

All operations are logged with:
- Call initiation and status updates
- Database operations
- API requests and responses
- Error details for debugging

Logs are stored in `app.log` and also output to console.

## Development

### Adding New Models

1. Update `prisma/schema.prisma`
2. Run `prisma generate`
3. Run `prisma db push`

### Database Migrations

For production, use Prisma migrations:

```bash
prisma migrate dev --name add_new_field
```

### Testing

Test the API endpoints using the provided examples or tools like Postman.

## Troubleshooting

### Common Issues

1. **Prisma Client Not Generated**
   - Run `prisma generate`

2. **Database Connection Failed**
   - Check `DATABASE_URL` in `.env`
   - Ensure SQLite file is writable

3. **Missing Environment Variables**
   - Verify all required variables in `.env`
   - Check `config.py` validation

4. **Twilio Errors**
   - Verify Twilio credentials
   - Check phone number format

### Debug Mode

Set `DEBUG=True` in `.env` for detailed logging and error messages.

## Production Deployment

For production:
1. Use a production database (PostgreSQL recommended)
2. Set `DEBUG=False`
3. Configure proper CORS origins
4. Use environment variables for all secrets
5. Set up proper logging and monitoring 