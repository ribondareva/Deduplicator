import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from redis.asyncio.cluster import RedisCluster, ClusterNode
from redis.exceptions import RedisError, ResponseError
from config import settings

logger = logging.getLogger(__name__)


class Deduplicator:
    def __init__(self):
        self.redis: Optional[RedisCluster] = None
        self.current_bloom_key = settings.REDIS_BLOOM_KEY
        self.last_bloom_reset_time: Optional[datetime] = None
        self.bloom_initialized = False

    async def _wait_for_cluster_ready(self, retries: int = 10, delay: int = 3) -> bool:
        """Ожидает, пока cluster_state не станет OK"""
        for attempt in range(1, retries + 1):
            try:
                raw_info = await self.redis.execute_command("CLUSTER INFO")
                info_lines = raw_info.splitlines()
                info_dict = dict(line.strip().split(":") for line in info_lines if ":" in line)
                cluster_state = info_dict.get("cluster_state")
                logger.debug(f"Cluster state check #{attempt}: {cluster_state}")
                if cluster_state == "ok":
                    return True
            except Exception as e:
                logger.debug(f"Cluster state check failed (attempt {attempt}): {e}")
            await asyncio.sleep(delay)

        logger.error("Cluster state did not become OK in time")
        return False

    async def init_redis(self) -> None:
        """Инициализация подключения к Redis Cluster и проверка модуля Bloom"""
        if self.redis is not None:
            return

        try:
            logger.info("Connecting to Redis Cluster...")

            logger.debug(f"Redis cluster nodes: {settings.REDIS_CLUSTER_NODES}")

            for attempt in range(10):
                try:
                    if self.redis:
                        await self.redis.close()

                    self.redis = RedisCluster(
                        startup_nodes=[ClusterNode(host=node["host"], port=node["port"])
                                       for node in settings.REDIS_CLUSTER_NODES],
                        decode_responses=True,
                        socket_timeout=10,
                        socket_connect_timeout=10,
                        cluster_error_retry_attempts=5,
                        require_full_coverage=False,
                        reinitialize_steps=10,
                    )

                    # Проверка подключения и статуса кластера
                    if await self._check_connection() and await self._wait_for_cluster_ready():
                        logger.info("Connected to Redis Cluster and cluster state is OK")
                        break

                except RedisError as e:
                    logger.error(f"Failed to connect to Redis Cluster (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(5)

            else:
                raise RedisError("Failed to connect to Redis Cluster after multiple attempts")

            if not await self._check_bloom_module():
                raise RedisError("RedisBloom module not loaded")

            await self.initialize_bloom_filter()
            logger.info("Redis Cluster connection established and Bloom filter initialized")

        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")
            await self._close_connection()
            raise RuntimeError(f"Redis initialization failed: {e}")

    async def _check_connection(self) -> bool:
        """Проверка подключения к Redis Cluster"""
        if not self.redis:
            return False

        try:
            response = await self.redis.execute_command("PING")
            return response == b"PONG" or response == "PONG"
        except Exception as e:
            logger.error(f"Redis cluster ping failed: {str(e)}")
            return False

    async def _check_bloom_module(self) -> bool:
        """Проверка наличия модуля RedisBloom"""
        try:
            modules = await self.redis.execute_command("MODULE LIST")
            logger.debug(f"Loaded Redis modules: {modules}")
            return any(b'bloom' in module for module in modules)
        except Exception as e:
            logger.error(f"Failed to check Redis modules: {e}")
            return False

    async def initialize_bloom_filter(self) -> None:
        """Инициализация Bloom фильтра с периодической переинициализацией"""
        now = datetime.now()
        if self.last_bloom_reset_time and (now - self.last_bloom_reset_time) < timedelta(hours=1):
            logger.debug(f"Bloom filter initialization skipped: last reset was {now - self.last_bloom_reset_time} ago")
            return

        try:
            # Создаем Bloom фильтр, если не существует
            await self.redis.execute_command(
                "BF.RESERVE",
                self.current_bloom_key,
                0.01,  # error rate
                1000000,  # capacity
                "EXPANSION", 2  # параметр масштабирования
            )
            self.last_bloom_reset_time = now
            self.bloom_initialized = True
            logger.info(f"Bloom filter {self.current_bloom_key} initialized")
        except ResponseError as e:
            if "item exists" not in str(e):
                logger.error(f"Bloom filter reserve failed: {e}")
                raise
            logger.debug("Bloom filter already exists")
        except Exception as e:
            logger.error(f"Bloom filter initialization failed: {e}")
            raise RuntimeError(f"Bloom filter init failed: {e}")

    async def is_unique(self, item_id: str) -> bool:
        """Проверка уникальности элемента через Bloom фильтр и TTL-ключ"""
        if not self.redis or not self.bloom_initialized:
            raise RuntimeError("Redis connection not initialized")

        try:
            # Явное использование execute_command для EXISTS в кластере
            ttl_key = f"bloom_expire:{item_id}"
            exists = await self.redis.execute_command("EXISTS", ttl_key)

            if exists:
                logger.debug(f"Item {item_id} found in TTL keys (duplicate)")
                return False

            # Проверка Bloom фильтра
            bloom_exists = await self.redis.execute_command(
                "BF.EXISTS",
                self.current_bloom_key,
                item_id
            )
            return not bloom_exists

        except Exception as e:
            logger.error(f"Uniqueness check failed for {item_id}: {e}")
            raise RuntimeError(f"Uniqueness check failed: {e}")

    async def add_to_bloom(self, item_id: str, ttl_seconds: int = 3600) -> None:
        """Добавление элемента в Bloom фильтр и установка TTL-ключа"""
        if not self.redis or not self.bloom_initialized:
            raise RuntimeError("Redis connection not initialized")

        try:
            # Добавляем в Bloom фильтр
            await self.redis.execute_command("BF.ADD", self.current_bloom_key, item_id)

            # Проверка, существует ли TTL ключ
            ttl_key = f"bloom_expire:{item_id}"
            ttl_exists = await self.redis.execute_command("EXISTS", ttl_key)

            if not ttl_exists:
                # Устанавливаем TTL-ключ, если он еще не существует
                await self.redis.execute_command("SETEX", ttl_key, ttl_seconds, "1")
                logger.debug(f"Added {item_id} to Bloom filter with {ttl_seconds}s TTL")
            else:
                logger.debug(f"TTL key {ttl_key} already exists, skipping SETEX")

        except Exception as e:
            logger.error(f"Failed to add {item_id} to Bloom: {e}")
            raise RuntimeError(f"Failed to add to Bloom: {e}")

    async def _close_connection(self) -> None:
        """Безопасное закрытие соединения"""
        if self.redis:
            try:
                await self.redis.close()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self.redis = None
                self.bloom_initialized = False


async def get_deduplicator() -> Deduplicator:
    """Фабрика для создания Deduplicator с инициализированным соединением"""
    deduplicator = Deduplicator()
    await deduplicator.init_redis()
    return deduplicator
