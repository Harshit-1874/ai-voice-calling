import redis.asyncio as redis
import logging
import asyncio

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self):
        self._client = None  # The actual aioredis client instance
        self._is_connected = False  # Keep track of logical connection state
        
        # Default configuration
        self._host = "localhost"
        self._port = 6379
        self._username = "default"
        self._password = None

        # Load configuration from config.py if available
        try:
            from config import REDIS_HOST_URI, REDIS_PASS
            # Parse host and port from REDIS_HOST_URI (if it contains a port)
            if REDIS_HOST_URI and ':' in REDIS_HOST_URI:
                self._host, port_str = REDIS_HOST_URI.split(':', 1)
                self._port = int(port_str)
            else:
                self._host = REDIS_HOST_URI if REDIS_HOST_URI else self._host
                # Assuming your Redis Cloud instance uses a specific port if only host is provided
                self._port = 11068 if REDIS_HOST_URI and REDIS_HOST_URI != "localhost" else self._port 
            self._password = REDIS_PASS
            logger.info(f"Redis configuration loaded from config.py - Host: {self._host}, Port: {self._port}")
        except ImportError:
            logger.warning("config.py not found or REDIS_HOST_URI/REDIS_PASS not set. Using default Redis connection parameters (localhost:6379, no password).")
        except Exception as e:
            logger.error(f"Error loading Redis config: {e}. Using default parameters.")

        logger.info("RedisService initialized.")

    async def connect(self):
        """Initializes the async Redis client and tests connection."""
        if self._is_connected and self._client:
            try:
                await self._client.ping()  # Verify existing connection
                logger.debug("Redis client already connected and responsive.")
                return
            except Exception:
                logger.warning("Existing Redis client is not responsive, attempting re-connection.")
                await self.disconnect()  # Force disconnect stale connection

        if self._client is None:  # Only create new client if it doesn't exist or was just disconnected
            try:
                self._client = redis.Redis(
                    host=self._host,
                    port=self._port,
                    username=self._username,
                    password=self._password,
                    decode_responses=True,  # Important for getting strings back
                    encoding="utf-8",
                    socket_connect_timeout=5,  # Add a timeout
                    socket_timeout=5  # Add a timeout for read/write operations
                )
                await self._client.ping()  # Test connection immediately
                self._is_connected = True
                logger.info(f"Connected to Redis at {self._host}:{self._port} successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis at {self._host}:{self._port}: {e}")
                self._is_connected = False
                self._client = None  # Explicitly set to None if connection fails
                raise  # Re-raise to propagate connection errors

    async def disconnect(self):
        """Closes the Redis client connection pool."""
        if self._client and self._is_connected:
            try:
                await self._client.close()
                await self._client.connection_pool.disconnect()  # Ensure physical connections are closed
                self._is_connected = False
                self._client = None
                logger.info("Disconnected from Redis.")
            except Exception as e:
                logger.error(f"Error during Redis disconnection: {e}")
                self._is_connected = False  # Mark as disconnected even on error

    @property
    def client(self):
        """Returns the async Redis client instance. Users should ensure connection."""
        return self._client

    async def __aenter__(self):
        """Context manager entry: ensures connection before yielding client."""
        await self.connect()  # Ensure connection when entering context
        if not self._is_connected or not self._client:
            raise RuntimeError("Redis client is not connected inside __aenter__")
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: disconnects on exit."""
        # Note: In FastAPI, often connections are managed at app startup/shutdown
        # but for individual WebSocket lifecycles, this is also valid.
        await self.disconnect()