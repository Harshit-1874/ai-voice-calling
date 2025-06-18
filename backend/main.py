import logging
import sys
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from routes.call_routes import router as call_router
from config import validate_env, HOST, PORT, DEBUG

current_dir = Path(__file__).parent
log_file = current_dir / "app.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info("="*50)
logger.info("Application Starting")
logger.info(f"Start Time: {datetime.now()}")
logger.info(f"Log file location: {log_file}")
logger.info("="*50)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application lifespan")
    validate_env()
    logger.info("All environment variables validated")
    yield
    logger.info("Shutting down server...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(call_router)

if __name__ == "__main__":
    try:
        logger.info("Starting uvicorn server")
        uvicorn.run(
            app, 
            host=HOST, 
            port=PORT,
            log_level="debug",
            reload=False,
            workers=1,
            loop="asyncio"
        )
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        raise 