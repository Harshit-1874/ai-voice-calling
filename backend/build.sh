#!/bin/bash

# Render build script to handle Prisma binaries properly

echo "🚀 Starting Render build process..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r backend/requirements.txt

# Navigate to backend directory
cd backend

# Set environment variable for Prisma binary target
export PRISMA_CLI_BINARY_TARGETS="native,debian-openssl-3.0.x,debian-openssl-1.1.x,linux-musl-openssl-3.0.x,rhel-openssl-1.0.x"

echo "🔧 Generating Prisma client with correct binary targets..."

# Generate Prisma client with explicit binary targets
prisma generate --schema=./prisma/schema.prisma

# Verify Prisma client generation
if [ $? -eq 0 ]; then
    echo "✅ Prisma client generated successfully!"
else
    echo "❌ Prisma client generation failed!"
    exit 1
fi

echo "🎉 Build completed successfully!"
