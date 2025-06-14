# AI Voice Calling Bot

An AI-powered outbound calling system that integrates with CRM systems and uses OpenAI's Realtime API for natural voice conversations.

## Features

- Outbound calling capabilities using Twilio
- Inbound call handling
- Integration with CRM systems (HubSpot/Zoho)
- Real-time voice conversations using OpenAI's Realtime API
- Conversation logging and storage
- Lead qualification and CRM updates

## Technical Architecture

### Components

1. **Backend Service**
   - Node.js/Express server
   - WebSocket server for real-time communication
   - CRM integration module
   - Database for storing conversation logs and user data

2. **Voice Processing**
   - Twilio integration for telephony
   - OpenAI Realtime API integration for speech-to-speech
   - Voice activity detection
   - Conversation state management

3. **Data Storage**
   - Conversation logs
   - User information
   - Call metadata
   - Lead qualification data

### Data Flow

1. **Outbound Flow**
   - Retrieve contact data from CRM
   - Initiate call via Twilio
   - Establish WebSocket connection with OpenAI
   - Process real-time voice conversation
   - Log conversation and update CRM

2. **Inbound Flow**
   - Receive call via Twilio
   - Route to AI agent
   - Process conversation
   - Log and update CRM if needed

## Setup

### Prerequisites

- Node.js (v16 or higher)
- Twilio Account
- OpenAI API Key
- HubSpot/Zoho CRM Account
- MongoDB/PostgreSQL Database

### Environment Variables

```env
OPENAI_API_KEY=your_openai_api_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
CRM_API_KEY=your_crm_api_key
DATABASE_URL=your_database_url
```

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   cd backend
   npm install
   ```
3. Set up environment variables
4. Start the server:
   ```bash
   npm start
   ```

## Development Status

- [ ] Basic project setup
- [ ] Twilio integration
- [ ] OpenAI Realtime API integration
- [ ] CRM integration
- [ ] Database setup
- [ ] Conversation logging
- [ ] Lead qualification logic
- [ ] Error handling and monitoring

## API Documentation

(To be added as development progresses)

## Contributing

(To be added)

## License

(To be added)
