# логика работы с RedisBloom
import redis.asyncio as redis
from redis.exceptions import ResponseError
from config import settings


class Deduplicator:
    def __init__(self):
        self.redis = None

    async def init_redis(self):
        if self.redis is None:
            print("Initializing Redis connection...")
            self.redis = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)

            # Проверка и создание Redis Bloom Filter
            try:
                await self.redis.execute_command("BF.RESERVE", settings.REDIS_BLOOM_KEY, 0.01, 1000000)
                print(f"Bloom Filter {settings.REDIS_BLOOM_KEY} initialized successfully.")
            except ResponseError:
                pass
            except Exception as e:
                print(f"Redis initialization failed: {e}")
                raise RuntimeError(f"Failed to initialize Redis: {e}")

    async def is_unique(self, item_id: str) -> bool:
        try:
            print(f"Checking uniqueness for item_id: {item_id}")
            result = not await self.redis.execute_command("BF.EXISTS", settings.REDIS_BLOOM_KEY, item_id)
            print(f"Item_id {item_id} uniqueness check result: {result}")
            return result
        except Exception as e:
            print(f"Error checking uniqueness in Redis: {e}")
            raise RuntimeError(f"Error checking uniqueness in Redis: {e}")

    async def add_to_bloom(self, item_id: str):
        try:
            print(f"Adding item_id to Bloom: {item_id}")
            await self.redis.execute_command("BF.ADD", settings.REDIS_BLOOM_KEY, item_id)
            print(f"Item_id {item_id} added to Bloom filter successfully")
        except Exception as e:
            print(f"Error adding item {item_id} to Bloom filter: {e}")
            raise RuntimeError(f"Error adding item to Bloom Filter: {e}")


async def get_deduplicator() -> Deduplicator:
    deduplicator = Deduplicator()
    await deduplicator.init_redis()
    return deduplicator
