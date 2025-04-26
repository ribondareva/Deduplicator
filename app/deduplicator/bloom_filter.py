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

RedisClient = Union[Redis, RedisCluster]


class Deduplicator:
    def __init__(self):
        self.redis: Optional[RedisClient] = None
        self.redis_connection: Optional[RedisClient] = None
        self.current_bloom_key = settings.REDIS_BLOOM_KEY
        self.last_bloom_reset_time: Optional[datetime] = None
        self.bloom_initialized = False
        self.bloom_supported = True
        self.cluster_nodes = settings.REDIS_CLUSTER_NODES

    async def _wait_for_cluster_ready(self, retries: int = 10, delay: int = 3) -> bool:
        startup_node = self.cluster_nodes[0]
        logger.debug("Attempting to connect to Redis node %s:%s", startup_node['host'], startup_node['port'])

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
                        info_dict = dict(
                            line.strip().split(":")
                            for line in cluster_info.splitlines()
                            if ":" in line
                        )
                    else:
                        info_dict = cluster_info

                    cluster_state = info_dict.get("cluster_state")
                    slots_assigned = int(info_dict.get("cluster_slots_assigned", "0"))

                    logger.debug("Cluster check #%s: state=%s, slots=%s", attempt, cluster_state, slots_assigned)

                    if cluster_state == "ok" and slots_assigned == 16384:
                        logger.info("Redis Cluster is ready")
                        return True

            except Exception as e:
                logger.warning("Cluster check failed (attempt %s): %s", attempt, e)

            await asyncio.sleep(delay)

        logger.error("Cluster did not become ready")
        return False

    async def wait_for_cluster_ready(self, retries: int = 10, delay: int = 3) -> bool:
        """
        Публичный метод для проверки готовности кластера.
        Используется для ожидания готовности Redis-кластера.
        """
        return await self._wait_for_cluster_ready(retries, delay)

    async def init_redis(self) -> None:
        if self.redis is not None:
            return

        try:
            logger.info("Initializing Redis Cluster connection...")

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
            self.redis_connection = self.redis

            self.bloom_supported = await self._check_bloom_module()
            if not self.bloom_supported:
                logger.warning("RedisBloom module not available, falling back to basic SET operations")

            if not await self._check_connection():
                raise RedisError("Connection test failed")

            if self.bloom_supported:
                await self.initialize_bloom_filter()

            logger.info("Redis Cluster initialized successfully. Bloom support: %s", self.bloom_supported)

        except RedisError as e:
            logger.error("Redis initialization failed: %s", e)
            await self._close_connection()
            raise RuntimeError("Redis initialization failed: %s" % e) from e
        except Exception as e:
            logger.error("Unexpected error during Redis initialization: %s", e)
            await self._close_connection()
            raise RuntimeError("Unexpected error during Redis initialization: %s" % e) from e

    async def _check_connection(self) -> bool:
        try:
            if self.redis is None:
                logger.error("Redis client is not initialized.")
                return False
            return await self.redis.ping()
        except Exception as e:
            logger.error("Connection check failed: %s", e)
            return False

    async def _check_bloom_module(self) -> bool:
        try:
            if self.redis is None:
                logger.error("Redis client is not initialized.")
                return False

            test_key = "temp_bloom_check_%s" % datetime.now().timestamp()
            try:
                await self.redis.execute_command("BF.ADD", test_key, "test_value")
                await self.redis.execute_command("DEL", test_key)
                return True

            except ResponseError as e:
                if "unknown command" in str(e).lower():
                    logger.warning("RedisBloom module is not installed.")
                    return False
                return True

        except Exception as e:
            logger.error("Bloom module check failed: %s", e)
            return False

    async def initialize_bloom_filter(self) -> None:
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
            logger.info("Bloom filter initialized: %s", self.current_bloom_key)
        except ResponseError as e:
            if "item exists" not in str(e):
                raise
            logger.debug("Bloom filter already exists")
            self.bloom_initialized = True
        except Exception as e:
            logger.error("Bloom filter init failed: %s", e)
            self.bloom_supported = False
            raise

    async def is_unique(self, item_id: str) -> bool:
        if not self.redis:
            raise RuntimeError("Redis is not initialized. Please call 'init_redis' first.")

        try:
            ttl_key = "bloom_ttl:%s" % item_id
            if await self.redis.exists(ttl_key):
                return False

            if self.bloom_supported and self.bloom_initialized:
                return not await self.redis.execute_command(
                    "BF.EXISTS",
                    self.current_bloom_key,
                    item_id
                )
            return not await self.redis.exists("dedup:%s" % item_id)

        except Exception as e:
            logger.error("Uniqueness check failed: %s", e)
            raise RuntimeError("Uniqueness check failed: %s" % e)

    async def add_to_bloom(self, item_id: str, ttl_seconds: int = 3600) -> None:
        if not self.redis:
            raise RuntimeError("Redis is not initialized. Please call 'init_redis' first.")

        try:
            ttl_key = "bloom_ttl:%s" % item_id

            if self.bloom_supported and self.bloom_initialized:
                await self.redis.execute_command(
                    "BF.ADD",
                    self.current_bloom_key,
                    item_id
                )
            else:
                await self.redis.setex("dedup:%s" % item_id, ttl_seconds, 1)

            if not await self.redis.exists(ttl_key):
                await self.redis.setex(ttl_key, ttl_seconds, 1)

        except Exception as e:
            logger.error("Failed to add to Bloom: %s", e)
            raise RuntimeError("Failed to add to Bloom: %s" % e)

    async def _close_connection(self) -> None:
        if self.redis:
            try:
                await self.redis.close()
            except Exception as e:
                logger.error("Error closing connection: %s", e)
            finally:
                self.redis = None
                self.bloom_initialized = False

    async def close(self):
        await self._close_connection()


deduplicator = Deduplicator()
