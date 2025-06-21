# AI Voice Calling Application - Docker Setup

This guide will help you run the complete AI Voice Calling application using Docker and Docker Compose.

## Prerequisites

- Docker installed on your system
- Docker Compose installed on your system
- Your API keys and credentials ready

## Quick Start

### 1. Set up Environment Variables

Create a `.env` file in the root directory with your credentials:

```bash
# Database Configuration
DATABASE_URL="file:./voice_calling.db"

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=your_twilio_phone_number_here

# HubSpot Configuration
HUBSPOT_ACCESS_TOKEN=your_hubspot_access_token_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Server Configuration
BASE_URL=your_base_url_here
PORT=8000
HOST=0.0.0.0
DEBUG=True
```

### 2. Build and Run the Application

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode
docker-compose up --build -d
```

### 3. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Docker Services

### Backend Service (`ai-voice-backend`)
- **Port**: 8000
- **Technology**: FastAPI with Python 3.11
- **Database**: SQLite with Prisma ORM
- **Features**: 
  - REST API endpoints
  - WebSocket connections
  - Twilio integration
  - OpenAI integration
  - HubSpot integration
  - Automatic database initialization
  - Prisma client generation

### Frontend Service (`ai-voice-frontend`)
- **Port**: 5173
- **Technology**: React with Vite (Development Server)
- **Features**:
  - Modern UI with Tailwind CSS
  - Real-time call management
  - Contact management
  - Dashboard and analytics
  - Hot reload for development

## Docker Commands

### Basic Commands

```bash
# Start all services
docker-compose up

# Start in detached mode
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs

# View logs for specific service
docker-compose logs backend
docker-compose logs frontend

# Rebuild and restart
docker-compose up --build

# Remove all containers and volumes
docker-compose down -v
```

### Development Commands

```bash
# Access backend container
docker-compose exec backend bash

# Access frontend container
docker-compose exec frontend sh

# View real-time logs
docker-compose logs -f

# Restart specific service
docker-compose restart backend
docker-compose restart frontend
```

### Database Commands

```bash
# Initialize database (first time only)
docker-compose exec backend python init_db.py

# Generate Prisma client
docker-compose exec backend prisma generate

# Run database migrations
docker-compose exec backend prisma migrate deploy

# Reset database (WARNING: This will delete all data)
docker-compose exec backend prisma migrate reset

# View database schema
docker-compose exec backend prisma db pull

# Push schema changes to database
docker-compose exec backend prisma db push
```

### Database Management with Prisma Studio

To access the database GUI (Prisma Studio) from your host machine:

1. **Start Prisma Studio in the container:**
   ```bash
   docker-compose exec backend prisma studio --hostname 0.0.0.0 --port 5555
   ```

2. **Access it from your browser:**
   - Open: http://localhost:5555
   - This will show you all your database tables and data

3. **Alternative: Port forwarding**
   Add this to your `docker-compose.yml` under the backend service:
   ```yaml
   ports:
     - "8000:8000"
     - "5555:5555"  # For Prisma Studio
   ```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TWILIO_ACCOUNT_SID` | Your Twilio Account SID | `AC1fc6a5932d6861ed868236048d9ce2d5` |
| `TWILIO_AUTH_TOKEN` | Your Twilio Auth Token | `813bbbd2f66b6d2c07936469324be8dd` |
| `TWILIO_PHONE_NUMBER` | Your Twilio Phone Number | `+447808221001` |
| `OPENAI_API_KEY` | Your OpenAI API Key | `sk-proj-...` |
| `HUBSPOT_ACCESS_TOKEN` | Your HubSpot Access Token | `pat-na2-...` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `file:./voice_calling.db` |
| `BASE_URL` | Base URL for the application | `http://localhost:8000` |
| `PORT` | Backend port | `8000` |
| `HOST` | Backend host | `0.0.0.0` |
| `DEBUG` | Debug mode | `True` |

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   lsof -i :8000
   lsof -i :5173
   
   # Stop the conflicting service or change ports in docker-compose.yml
   ```

2. **Database Connection Issues**
   ```bash
   # Reinitialize the database
   docker-compose exec backend python init_db.py
   
   # Check database file permissions
   docker-compose exec backend ls -la prisma/
   
   # Check if database file exists
   docker-compose exec backend ls -la prisma/voice_calling.db
   ```

3. **Prisma Client Not Generated**
   ```bash
   # Generate Prisma client
   docker-compose exec backend prisma generate
   
   # Check if client files exist
   docker-compose exec backend ls -la prisma/
   
   # Restart backend after generating
   docker-compose restart backend
   ```

4. **Environment Variables Not Loading**
   ```bash
   # Check if .env file exists
   ls -la .env
   
   # Verify environment variables in container
   docker-compose exec backend env | grep TWILIO
   
   # Check if .env file is being read
   docker-compose exec backend cat /app/.env
   ```

5. **Build Failures**
   ```bash
   # Clean up and rebuild
   docker-compose down
   docker system prune -f
   docker-compose up --build
   ```

6. **Frontend Not Loading**
   ```bash
   # Check if Vite dev server is running
   docker-compose logs frontend
   
   # Restart frontend service
   docker-compose restart frontend
   ```

7. **Database Schema Issues**
   ```bash
   # Reset database completely
   docker-compose exec backend prisma migrate reset --force
   
   # Push schema changes
   docker-compose exec backend prisma db push
   
   # Pull current schema
   docker-compose exec backend prisma db pull
   ```

### Health Checks

The application includes health checks for both services:

```bash
# Check service health
docker-compose ps

# View health check logs
docker-compose logs backend | grep health
docker-compose logs frontend | grep health
```

### Logs and Debugging

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs backend
docker-compose logs frontend

# Follow logs in real-time
docker-compose logs -f

# View logs with timestamps
docker-compose logs -t

# View logs for specific time period
docker-compose logs --since="2024-01-01T00:00:00" backend
```

## Development vs Production

### Development Setup (Current)
- Frontend runs with Vite dev server on port 5173
- Hot reload enabled for fast development
- No build step required
- Direct access to source files
- SQLite database for simplicity
- Automatic database initialization

### Production Setup
For production deployment, you would need to:
1. Build the frontend for production
2. Use a production web server (Nginx, Apache)
3. Configure proper SSL/TLS
4. Set up proper environment variables
5. Use a production database (PostgreSQL, MySQL)
6. Set up proper logging and monitoring

## Support

If you encounter any issues:

1. Check the logs: `docker-compose logs`
2. Verify environment variables are set correctly
3. Ensure all required services are running
4. Check the troubleshooting section above
5. Try the database management commands if you have schema issues

For additional help, refer to the main README.md file or create an issue in the repository. 