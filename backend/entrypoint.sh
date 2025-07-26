#!/bin/bash

# Exit on any error
set -e

echo "🚀 Starting AI Voice Calling Backend..."

# Ensure the prisma directory and database file exist
echo "📁 Setting up database directory..."
mkdir -p /app/prisma
touch /app/prisma/voice_calling.db

# Check if database exists, if not initialize it
if [ ! -s "/app/prisma/voice_calling.db" ]; then
    echo "📊 Initializing database..."
    python init_db.py
    echo "✅ Database initialized successfully"
else
    echo "📊 Database already exists, skipping initialization"
fi

# Generate Prisma client (in case it wasn't generated during build)
echo "🔧 Generating Prisma client..."
prisma generate

# Start Celery worker in background
echo "🔄 Starting Celery worker..."
celery -A celery_app.celery_app worker --loglevel=info --pool=solo &

# Start the application
echo "🌐 Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
