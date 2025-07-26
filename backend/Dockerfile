FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Generate Prisma client
RUN prisma generate

# Create data directory for database
RUN mkdir -p /app/data /app/prisma

# Create a simple startup script
RUN echo '#!/bin/bash\n\
set -e\n\
echo "🚀 Starting AI Voice Calling Backend..."\n\
echo "📊 Using PostgreSQL database via SUPABASE_URL"\n\
echo "🔧 Generating Prisma client..."\n\
prisma generate\n\
echo "🌐 Starting FastAPI server..."\n\
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload' > /app/run.sh && chmod +x /app/run.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the startup script
CMD ["/bin/bash", "/app/run.sh"] 