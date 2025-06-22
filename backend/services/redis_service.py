from config import REDIS_PASS, REDIS_HOST_URI
import redis

class RedisService:
    client = None

    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST_URI,
            port=11068,
            decode_responses=True,
            username="default",
            password=REDIS_PASS,
        )