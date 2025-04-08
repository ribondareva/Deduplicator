# логика работы с RedisBloom
import redis.asyncio as redis
from redis.exceptions import ResponseError
from config import settings


class Deduplicator:
    def __init__(self):
        self.redis = None

    async def init_redis(self):
        # Инициализация соединения с Redis через redis.asyncio
        self.redis = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)

        # Проверка и создание Redis Bloom Filter
        try:
            await self.redis.execute_command("BF.RESERVE", settings.REDIS_BLOOM_KEY, 0.01, 1000000)
        except ResponseError:
            # Если фильтр уже существует, игнорируем ошибку
            pass

    async def is_unique(self, item_id: str) -> bool:
        # Проверка на уникальность в Bloom Filter
        return not await self.redis.execute_command("BF.EXISTS", settings.REDIS_BLOOM_KEY, item_id)

    async def add_to_bloom(self, item_id: str):
        # Добавление элемента в Bloom Filter
        await self.redis.execute_command("BF.ADD", settings.REDIS_BLOOM_KEY, item_id)

