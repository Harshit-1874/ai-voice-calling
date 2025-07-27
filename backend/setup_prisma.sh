#!/bin/bash

# Prisma binary setup script for Render deployment

echo "🔧 Setting up Prisma binaries for Linux deployment..."

# Install dependencies
pip install -r requirements.txt

# Set Prisma environment variables for Linux
export PRISMA_CLI_BINARY_TARGETS="debian-openssl-3.0.x"
export PRISMA_QUERY_ENGINE_BINARY="debian-openssl-3.0.x" 

# Generate Prisma client
echo "📦 Generating Prisma client..."
python -m prisma generate --schema=./prisma/schema.prisma

# Check if binary exists and create symbolic link if needed
PRISMA_BINARY_PATH="/opt/render/.cache/prisma-python/binaries/5.17.0/393aa359c9ad4a4bb28630fb5613f9c281cde053/prisma-query-engine-debian-openssl-3.0.x"
LOCAL_BINARY_PATH="./prisma-query-engine-debian-openssl-3.0.x"

if [ -f "$PRISMA_BINARY_PATH" ]; then
    echo "✅ Prisma binary found in cache, creating symbolic link..."
    ln -sf "$PRISMA_BINARY_PATH" "$LOCAL_BINARY_PATH"
elif [ -f "$LOCAL_BINARY_PATH" ]; then
    echo "✅ Local Prisma binary found"
    chmod +x "$LOCAL_BINARY_PATH"
else
    echo "⚠️  Prisma binary not found, but continuing..."
fi

echo "🎉 Prisma setup completed!"
