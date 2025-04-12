import json
from aiokafka import AIOKafkaConsumer
from app.api.schemas import EventSchema
from app.config import settings
from deduplicator.db import Database
from deduplicator.bloom_filter import Deduplicator

KAFKA_BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
KAFKA_TOPIC_NAME = settings.KAFKA_TOPIC_NAME

db = Database()
deduplicator = Deduplicator()


# Перед началом работы с Redis в консюмере
async def init_redis_in_consumer():
    if deduplicator.redis is None:
        await deduplicator.init_redis()


async def main():
    await init_redis_in_consumer()
    await db.init_db()

    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC_NAME,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()

    try:
        async for msg in consumer:
            try:
                event = EventSchema(**msg.value)
            except Exception as e:
                print(f"Invalid event data: {e}")
                continue

            item_id = event.product_id
            if not item_id:
                print("Invalid event: no product_id")
                continue

            # проверим наличие в базе данных
            if await db.check_event_exists(item_id):
                print(f"Duplicate event in DB: {item_id}")
                continue

            # проверим наличие в RedisBloom
            if not await deduplicator.is_unique(item_id):
                print(f"Duplicate event (Bloom): {item_id}")
                continue

            await db.insert_event(event)
            await deduplicator.add_to_bloom(item_id)
            print(f"Saved unique event: {item_id}")

    finally:
        await consumer.stop()
        await db.close_db()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
