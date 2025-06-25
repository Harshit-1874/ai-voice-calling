#!/bin/bash

# Exit on any error
set -e

echo "🚀 Starting AI Voice Calling Backend..."

# Check if database exists, if not initialize it
if [ ! -f "/app/prisma/voice_calling.db" ]; then
    echo "📊 Initializing database..."
    python init_db.py
    echo "✅ Database initialized successfully"
else
    echo "📊 Database already exists, skipping initialization"
fi

# Generate Prisma client (in case it wasn't generated during build)
echo "🔧 Generating Prisma client..."
prisma generate

# Start the application
echo "🌐 Starting FastAPI server..."
exec celery -A celery_app.celery_app worker --loglevel=info --pool=solo
exec uvicorn main:app --host 0.0.0.0 --port 8000 