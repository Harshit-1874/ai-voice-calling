import subprocess
import sys
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

async def ensure_prisma_setup():
    """Ensure Prisma is properly set up for deployment"""
    try:
        logger.info("🔧 Checking Prisma setup...")
        
        # Set environment variables for Prisma
        os.environ["PRISMA_CLI_BINARY_TARGETS"] = "debian-openssl-3.0.x"
        os.environ["PRISMA_QUERY_ENGINE_BINARY"] = "debian-openssl-3.0.x"
        
        # Check if we're in a deployment environment
        is_deployment = os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PORT", "").startswith("10")
        
        if is_deployment:
            logger.info("🚀 Deployment environment detected, setting up Prisma...")
            
            # Try to fetch binaries if not already present
            try:
                result = subprocess.run([
                    sys.executable, "-m", "prisma", "py", "fetch"
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    logger.info("✅ Prisma binaries fetched successfully")
                else:
                    logger.warning(f"⚠️ Prisma fetch warning: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Prisma fetch timed out, continuing...")
            except Exception as e:
                logger.warning(f"⚠️ Prisma fetch failed: {e}")
        
        # Test Prisma connection
        try:
            from services.prisma_service import prisma_service
            logger.info("✅ Prisma service imported successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Prisma service import failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Prisma setup failed: {e}")
        return False
