import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from app.api.schemas import EventSchema
from app.config import settings
from deduplicator.bloom_filter import Deduplicator
from deduplicator.db import Database, get_event_hash
from logger_config import setup_logger

setup_logger()
logger = logging.getLogger(__name__)

# Глобальные объекты
deduplicator = Deduplicator()
db = Database()

KAFKA_BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
KAFKA_TOPIC_NAME = settings.KAFKA_TOPIC_NAME


async def init_services():
    """Инициализация Redis и базы данных."""
    logger.info("Initializing services...")

    # Инициализируем Redis
    await deduplicator.init_redis()
    redis_ready = await deduplicator.wait_for_cluster_ready()
    if not redis_ready:
        raise RuntimeError("Redis cluster is not ready")

    # Инициализируем подключение к базе данных
    await db.init_db()

    logger.info("Services initialized successfully")


async def shutdown_services():
    """Корректное завершение работы с Redis и БД."""
    logger.info("Shutting down services...")
    await deduplicator.close()
    await db.close_db()
    logger.info("Services shut down successfully")


async def periodic_bloom_reinitialization(interval_minutes: int = 60):
    """Периодическая переинициализация Bloom-фильтра."""
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            logger.info("Periodic Bloom filter reinitialization started")
            await deduplicator.initialize_bloom_filter()
            logger.info("Bloom filter reinitialized successfully")
        except Exception as e:
            logger.error("Error during Bloom filter reinitialization: %s", e)
            await asyncio.sleep(60)  # маленькая задержка на случай фейла


async def process_event(event_data: dict):
    """Обработка одного события."""
    try:
        event = EventSchema(**event_data)
    except Exception as e:
        logger.error("Invalid event data: %s", e)
        return

    if not event.product_id:
        logger.error("Invalid event: missing product_id")
        return

    item_id = event.product_id
    event_hash = get_event_hash(event)

    # Проверяем наличие в базе
    if await db.check_event_exists(event_hash):
        logger.info("Duplicate event found in DB: %s", event_hash)
        return

    # Проверяем через Bloom-фильтр
    if not await deduplicator.is_unique(item_id):
        logger.info("Duplicate event detected by Bloom filter: %s", item_id)
        return

    # Сохраняем в базу
    try:
        await db.insert_event(event, event_hash)
        await deduplicator.add_to_bloom(item_id)
        logger.info("Saved unique event: %s", item_id)
    except Exception as e:
        logger.error("Failed to save event %s: %s", item_id, e)


async def consume_messages(consumer: AIOKafkaConsumer):
    """Основной цикл обработки сообщений из Kafka."""
    async for msg in consumer:
        logger.info("Received message: %s", msg.value)
        try:
            await process_event(msg.value)
        except Exception as e:
            logger.error("Error processing message: %s", e)


async def main():
    """Точка входа."""
    await init_services()

    # Запуск периодического обновления Bloom-фильтра
    asyncio.create_task(periodic_bloom_reinitialization())

    consumer = AIOKafkaConsumer(
        # KAFKA_TOPIC_NAME,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="deduplication-consumer-group",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )

    await consumer.start()
    logger.info("Kafka consumer started")
    consumer.subscribe([KAFKA_TOPIC_NAME])
    logger.info("Subscribed to topic: %s", KAFKA_TOPIC_NAME)

    try:
        await consume_messages(consumer)
    finally:
        await consumer.stop()
        await shutdown_services()
        logger.info("Kafka consumer stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())
