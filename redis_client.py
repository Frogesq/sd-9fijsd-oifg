import redis.asyncio as redis
from config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def get_redis():
    return redis_client
