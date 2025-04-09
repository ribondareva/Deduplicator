import json
from aiokafka import AIOKafkaConsumer
from app.api.schemas import EventSchema
from deduplicator.db import Database
from deduplicator.bloom_filter import Deduplicator

KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_TOPIC = "events"

db = Database()
deduplicator = Deduplicator()


async def main():
    await deduplicator.init_redis()
    await db.init_db()

    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
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

            # Проверка уникальности через Bloom Filter
            if not await deduplicator.is_unique(item_id):
                print(f"Duplicate event (Bloom): {item_id}")
                continue

            await deduplicator.add_to_bloom(item_id)

            if await db.check_event_exists(item_id):
                print(f"Duplicate event in DB: {item_id}")
                continue

            await db.insert_event(event)
            print(f"Saved unique event: {item_id}")

    finally:
        await consumer.stop()
        await db.close_db()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
