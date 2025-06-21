#!/usr/bin/env python3
"""
Database initialization script for Prisma with SQLite
"""
import os
import subprocess
import sys
from pathlib import Path

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return None

def main():
    """Main initialization function"""
    print("🚀 Starting Prisma database initialization...")
    
    # Get the current directory
    current_dir = Path(__file__).parent
    os.chdir(current_dir)
    
    # Check if .env file exists
    env_file = current_dir / ".env"
    if not env_file.exists():
        print("⚠️  .env file not found. Creating one with default values...")
        with open(env_file, "w") as f:
            f.write("""# Database Configuration
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
""")
        print("✅ .env file created. Please update it with your actual credentials.")
    
    # Install Prisma CLI if not already installed
    print("📦 Checking Prisma installation...")
    prisma_version = run_command("prisma --version", "Checking Prisma version")
    if not prisma_version:
        print("📦 Installing Prisma CLI...")
        run_command("pip install prisma", "Installing Prisma Python client")
    
    # Generate Prisma client
    print("🔧 Generating Prisma client...")
    if not run_command("prisma generate", "Generating Prisma client"):
        print("❌ Failed to generate Prisma client")
        sys.exit(1)
    
    # Push the schema to the database
    print("🗄️  Pushing schema to database...")
    if not run_command("prisma db push", "Pushing database schema"):
        print("❌ Failed to push database schema")
        sys.exit(1)
    
    # Verify the database
    print("🔍 Verifying database setup...")
    if not run_command("prisma db pull", "Verifying database schema"):
        print("❌ Failed to verify database schema")
        sys.exit(1)
    
    print("🎉 Database initialization completed successfully!")
    print("\n📋 Next steps:")
    print("1. Update your .env file with actual credentials")
    print("2. Run 'python main.py' to start the server")
    print("3. Access the API at http://localhost:8000")

if __name__ == "__main__":
    main() 