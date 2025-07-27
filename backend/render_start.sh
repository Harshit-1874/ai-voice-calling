#!/bin/bash

# Render startup script for Python FastAPI backend

echo "Starting Render deployment..."

# Generate Prisma client
echo "Generating Prisma client..."
prisma generate

# Run database migrations (if needed)
echo "Running database migrations..."
# Uncomment the next line if you have migrations to run
# prisma migrate deploy

# Start the FastAPI application
echo "Starting FastAPI application..."
python main.py
