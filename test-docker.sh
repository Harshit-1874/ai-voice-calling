#!/bin/bash

echo "🧪 Testing Docker Compose Setup..."

# Clean up any existing containers
echo "🧹 Cleaning up existing containers..."
docker-compose down

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Test backend health endpoint
echo "🔍 Testing backend health endpoint..."
backend_health=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$backend_health" = "200" ]; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend health check failed (HTTP $backend_health)"
fi

# Test frontend
echo "🔍 Testing frontend..."
frontend_health=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173)
if [ "$frontend_health" = "200" ]; then
    echo "✅ Frontend is accessible"
else
    echo "❌ Frontend health check failed (HTTP $frontend_health)"
fi

# Show container status
echo "📊 Container status:"
docker-compose ps

echo "🎉 Test completed!"
