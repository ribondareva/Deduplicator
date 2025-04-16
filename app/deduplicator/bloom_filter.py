import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union

from redis.asyncio.cluster import RedisCluster
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from config import settings

logger = logging.getLogger(__name__)

# Тип для Redis клиента (кластерный или обычный)
RedisClient = Union[Redis, RedisCluster]


class Deduplicator:
    def __init__(self):
        self.redis: Optional[RedisClient] = None
        self.current_bloom_key = settings.REDIS_BLOOM_KEY
        self.last_bloom_reset_time: Optional[datetime] = None
        self.bloom_initialized = False
        self.bloom_supported = True  # Флаг поддержки Bloom фильтров
        self.cluster_nodes = settings.REDIS_CLUSTER_NODES

    async def _wait_for_cluster_ready(self, retries: int = 10, delay: int = 3) -> bool:
        """Ожидает готовности кластера Redis"""
        startup_node = self.cluster_nodes[0]
        logger.debug(f"Attempting to connect to Redis node {startup_node['host']}:{startup_node['port']}")

        for attempt in range(1, retries + 1):
            try:
                async with Redis(
                        host=startup_node["host"],
                        port=startup_node["port"],
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5
                ) as temp_client:
                    cluster_info = await temp_client.execute_command("CLUSTER INFO")
                    if isinstance(cluster_info, str):
                        info_dict = dict(line.strip().split(":")
                                         for line in cluster_info.splitlines()
                                         if ":" in line)
                    else:
                        info_dict = cluster_info

                    cluster_state = info_dict.get("cluster_state")
                    slots_assigned = int(info_dict.get("cluster_slots_assigned", "0"))

                    logger.debug(f"Cluster check #{attempt}: state={cluster_state}, slots={slots_assigned}")

                    if cluster_state == "ok" and slots_assigned == 16384:
                        logger.info("Redis Cluster is ready")
                        return True

            except Exception as e:
                logger.warning(f"Cluster check failed (attempt {attempt}): {e}")

            await asyncio.sleep(delay)

        logger.error("Cluster did not become ready")
        return False

    async def init_redis(self) -> None:
        """Инициализация подключения к Redis Cluster"""
        if self.redis is not None:
            return

        try:
            logger.info("Initializing Redis Cluster connection...")

            # Конфигурация для Redis Cluster
            cluster_params: Dict[str, Any] = {
                "host": self.cluster_nodes[0]["host"],
                "port": self.cluster_nodes[0]["port"],
                "decode_responses": True,
                "socket_timeout": 10,
                "socket_connect_timeout": 10,
                "read_from_replicas": True,
                "retry": Retry(ExponentialBackoff(), 3)
            }

            self.redis = RedisCluster(**cluster_params)

            self.bloom_supported = await self._check_bloom_module()
            if not self.bloom_supported:
                logger.warning("RedisBloom module not available, falling back to basic SET operations")

            if not await self._check_connection():
                raise RedisError("Connection test failed")

            if self.bloom_supported:
                await self.initialize_bloom_filter()

            logger.info(f"Redis Cluster initialized successfully. Bloom support: {self.bloom_supported}")

        except RedisError as e:
            logger.error(f"Redis initialization failed: {e}")
            await self._close_connection()
            raise RuntimeError(f"Redis initialization failed: {e}") from e

    async def _check_connection(self) -> bool:
        """Проверка соединения с кластером"""
        try:
            if self.redis is None:
                return False
            return await self.redis.ping()
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False

    async def _check_bloom_module(self) -> bool:
        """Проверка наличия модуля RedisBloom с правильными командами"""
        try:
            if self.redis is None:
                return False

            test_key = f"temp_bloom_check_{datetime.now().timestamp()}"
            try:
                await self.redis.execute_command(
                    "BF.ADD",
                    test_key,
                    "test_value"
                )

                # Очищаем тестовые данные
                await self.redis.execute_command("DEL", test_key)
                return True

            except ResponseError as e:
                if "unknown command" in str(e).lower():
                    return False
                return True

        except Exception as e:
            logger.error(f"Bloom module check failed: {e}")
            return False

    async def initialize_bloom_filter(self) -> None:
        """Инициализация Bloom-фильтра"""
        if not self.bloom_supported:
            return

        now = datetime.now()
        if self.last_bloom_reset_time and (now - self.last_bloom_reset_time) < timedelta(hours=1):
            logger.debug("Skipping Bloom filter reinitialization")
            return

        try:
            if self.redis is None:
                raise RedisError("Redis connection not established")

            await self.redis.execute_command(
                "BF.RESERVE",
                self.current_bloom_key,
                0.01,
                1000000,
                "EXPANSION", 2
            )
            self.last_bloom_reset_time = now
            self.bloom_initialized = True
            logger.info(f"Bloom filter initialized: {self.current_bloom_key}")
        except ResponseError as e:
            if "item exists" not in str(e):
                raise
            logger.debug("Bloom filter already exists")
            self.bloom_initialized = True
        except Exception as e:
            logger.error(f"Bloom filter init failed: {e}")
            self.bloom_supported = False
            raise

    async def is_unique(self, item_id: str) -> bool:
        """Проверка уникальности элемента"""
        if not self.redis:
            raise RuntimeError("Redis not initialized")

        try:
            ttl_key = f"bloom_ttl:{item_id}"
            if await self.redis.exists(ttl_key):
                return False

            if self.bloom_supported and self.bloom_initialized:
                return not await self.redis.execute_command(
                    "BF.EXISTS",
                    self.current_bloom_key,
                    item_id
                )
            return not await self.redis.exists(f"dedup:{item_id}")

        except Exception as e:
            logger.error(f"Uniqueness check failed: {e}")
            raise RuntimeError(f"Uniqueness check failed: {e}")

    async def add_to_bloom(self, item_id: str, ttl_seconds: int = 3600) -> None:
        """Добавление элемента в Bloom-фильтр"""
        if not self.redis:
            raise RuntimeError("Redis not initialized")

        try:
            ttl_key = f"bloom_ttl:{item_id}"

            if self.bloom_supported and self.bloom_initialized:
                await self.redis.execute_command(
                    "BF.ADD",
                    self.current_bloom_key,
                    item_id
                )
            else:
                await self.redis.setex(f"dedup:{item_id}", ttl_seconds, 1)

            if not await self.redis.exists(ttl_key):
                await self.redis.setex(ttl_key, ttl_seconds, 1)

        except Exception as e:
            logger.error(f"Failed to add to Bloom: {e}")
            raise RuntimeError(f"Failed to add to Bloom: {e}")

    async def _close_connection(self) -> None:
        """Закрытие соединения"""
        if self.redis:
            try:
                await self.redis.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                self.redis = None
                self.bloom_initialized = False


async def get_deduplicator() -> Deduplicator:
    deduplicator = Deduplicator()
    await deduplicator.init_redis()
    return deduplicator
