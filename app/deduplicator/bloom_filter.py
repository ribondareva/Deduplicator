# логика работы с RedisBloom
import redis.asyncio as redis
from redis.exceptions import ResponseError
from config import settings


class Deduplicator:
    def __init__(self):
        self.redis = None

    async def init_redis(self):
        self.redis = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)

        # Проверка и создание Redis Bloom Filter
        try:
            await self.redis.execute_command("BF.RESERVE", settings.REDIS_BLOOM_KEY, 0.01, 1000000)
        except ResponseError:
            pass
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Redis: {e}")

    async def is_unique(self, item_id: str) -> bool:
        try:
            return not await self.redis.execute_command("BF.EXISTS", settings.REDIS_BLOOM_KEY, item_id)
        except Exception as e:
            raise RuntimeError(f"Error checking uniqueness in Redis: {e}")

    async def add_to_bloom(self, item_id: str):
        try:
            await self.redis.execute_command("BF.ADD", settings.REDIS_BLOOM_KEY, item_id)
        except Exception as e:
            raise RuntimeError(f"Error adding item to Bloom Filter: {e}")

