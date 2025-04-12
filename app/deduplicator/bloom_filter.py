# логика работы с RedisBloom
from datetime import datetime, timedelta

import redis.asyncio as redis
from redis.exceptions import ResponseError
from config import settings


class Deduplicator:
    def __init__(self):
        self.redis = None
        self.current_bloom_key = settings.REDIS_BLOOM_KEY  # Один ключ на всю жизнь приложения
        self.last_bloom_reset_time = None  # Время последней переинициализации

    async def init_redis(self):
        if self.redis is None:
            print("Initializing Redis connection...")
            self.redis = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)
            # Проверка и создание Redis Bloom Filter
            await self.initialize_bloom_filter()

    async def initialize_bloom_filter(self):
        """ Переинициализация Bloom фильтра каждый час."""
        now = datetime.now()

        # Переинициализация, если прошло больше 1 часа с последней
        if not self.last_bloom_reset_time or (now - self.last_bloom_reset_time) > timedelta(hours=1):
            try:
                await self.redis.execute_command("BF.RESERVE", self.current_bloom_key, 0.01, 1000000)
                print(f"Bloom Filter {self.current_bloom_key} initialized successfully.")
                self.last_bloom_reset_time = now  # Обновляем время последней переинициализации
            except ResponseError:
                pass
            except Exception as e:
                print(f"Redis initialization failed: {e}")
                raise RuntimeError(f"Failed to initialize Redis: {e}")

    async def is_unique(self, item_id: str) -> bool:
        try:
            print(f"Checking uniqueness for item_id: {item_id}")
            # Сначала проверяем TTL-ключ
            exists = await self.redis.exists(f"bloom_expire:{item_id}")
            if exists:
                print(f"Item_id {item_id} is NOT unique (TTL key exists)")
                return False
            # Проверка Bloom-фильтра
            result = not await self.redis.execute_command("BF.EXISTS", self.current_bloom_key, item_id)
            print(f"Item_id {item_id} uniqueness check result: {result}")
            return result
        except Exception as e:
            print(f"Error checking uniqueness in Redis: {e}")
            raise RuntimeError(f"Error checking uniqueness in Redis: {e}")

    async def add_to_bloom(self, item_id: str, ttl_seconds: int = 3600):
        try:
            print(f"Adding item_id to Bloom: {item_id}")
            await self.redis.execute_command("BF.ADD", self.current_bloom_key, item_id)
            # Дополнительно сохраняем ключ с TTL
            await self.redis.set(f"bloom_expire:{item_id}", 1, ex=ttl_seconds)
            print(f"Item_id {item_id} added to Bloom filter successfully and TTL key set for {ttl_seconds} seconds")
        except Exception as e:
            print(f"Error adding item {item_id} to Bloom filter: {e}")
            raise RuntimeError(f"Error adding item to Bloom Filter: {e}")


async def get_deduplicator() -> Deduplicator:
    deduplicator = Deduplicator()
    await deduplicator.init_redis()
    return deduplicator
