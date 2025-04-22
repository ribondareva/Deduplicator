import json
import asyncio
import logging
from aiokafka import AIOKafkaConsumer
from app.api.schemas import EventSchema
from app.config import settings
from deduplicator.db import Database, get_event_hash
from deduplicator.bloom_filter import deduplicator, Deduplicator

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
KAFKA_TOPIC_NAME = settings.KAFKA_TOPIC_NAME

db = Database()


async def periodic_bloom_reinitialization(deduplicator: Deduplicator, interval_minutes: int = 60) -> None:
    """Периодическая переинициализация Bloom-фильтра"""
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            logger.info("Periodic Bloom filter reinitialization started")
            await deduplicator.initialize_bloom_filter()
            logger.info("Bloom filter reinitialized successfully")
        except Exception as e:
            logger.error("Error during periodic Bloom filter reinitialization: %s", e)
            await asyncio.sleep(60)


async def init_redis_in_consumer() -> None:
    """Инициализация подключения к Redis"""
    try:
        if deduplicator.redis is None:
            await deduplicator.init_redis()
            logger.info("Redis connected successfully")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise


async def process_event(event_data: dict) -> None:
    """Обработка одного события"""
    try:
        event = EventSchema(**event_data)
    except Exception as e:
        logger.error("Invalid event data: %s", e)
        return

    if not event.product_id:
        logger.error("Invalid event: no product_id")
        return

    item_id = event.product_id
    event_hash = get_event_hash(event)

    if await db.check_event_exists(event_hash):
        logger.info("Duplicate event in DB: %s", event_hash)
        return

    if not await deduplicator.is_unique(item_id):
        logger.info("Duplicate event (Bloom): %s", item_id)
        return

    try:
        await db.insert_event(event, event_hash)
        await deduplicator.add_to_bloom(item_id)
        logger.info("Saved unique event: %s", item_id)
    except Exception as e:
        logger.error("Failed to save event %s: %s", item_id, e)


async def consume_messages(consumer: AIOKafkaConsumer) -> None:
    """Основной цикл обработки сообщений"""
    try:
        async for msg in consumer:
            try:
                await process_event(msg.value)
            except Exception as e:
                logger.error("Error processing message: %s", e)
    except Exception as e:
        logger.error("Consumer error: %s", e)
        raise


async def main() -> None:
    """Основная функция"""
    try:
        await init_redis_in_consumer()
        await db.init_db()

        asyncio.create_task(periodic_bloom_reinitialization(deduplicator))

        consumer = AIOKafkaConsumer(
            KAFKA_TOPIC_NAME,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id="deduplication-consumer-group",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            enable_auto_commit=True,
            auto_offset_reset="earliest",
        )

        await consumer.start()
        logger.info("Consumer started successfully")

        try:
            await consume_messages(consumer)
        finally:
            await consumer.stop()
            await db.close_db()
            await deduplicator.close()
            logger.info("Consumer stopped gracefully")
    except Exception as e:
        logger.error("Fatal error in consumer: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
