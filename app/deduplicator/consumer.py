import json
from aiokafka import AIOKafkaConsumer
from app.api.schemas import EventSchema
from app.config import settings
from deduplicator.db import Database, get_event_hash
from deduplicator.bloom_filter import Deduplicator

KAFKA_BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
KAFKA_TOPIC_NAME = settings.KAFKA_TOPIC_NAME

db = Database()
deduplicator = Deduplicator()


async def periodic_bloom_reinitialization(deduplicator, interval_minutes=60):
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            print("Bloom filter reinitialized due to time interval.")
            await deduplicator.initialize_bloom_filter()
        except Exception as e:
            print(f"Error during periodic Bloom filter reinitialization: {e}")


# Перед началом работы с Redis в консюмере
async def init_redis_in_consumer():
    try:
        if deduplicator.redis is None:
            await deduplicator.init_redis()
            print("Redis connected successfully.")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        raise


async def main():
    try:
        await init_redis_in_consumer()
        await db.init_db()

        # Запуск задачи переинициализации Bloom фильтра каждый час
        # noinspection PyAsyncCall
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

        try:
            async for msg in consumer:
                try:
                    event = EventSchema(**msg.value)
                except Exception as e:
                    print(f"Invalid event data: {e}")
                    continue

                item_id = event.product_id
                event_hash = get_event_hash(event)
                if not item_id:
                    print("Invalid event: no product_id")
                    continue

                # проверим наличие в базе данных
                if await db.check_event_exists(event_hash):
                    print(f"Duplicate event in DB: {event_hash}")
                    continue

                # проверим наличие в RedisBloom
                if not await deduplicator.is_unique(item_id):
                    print(f"Duplicate event (Bloom): {item_id}")
                    continue

                await db.insert_event(event, event_hash)
                await deduplicator.add_to_bloom(item_id)
                print(f"Saved unique event: {item_id}")

        finally:
            await consumer.stop()
            await db.close_db()

    except Exception as e:
        print(f"Error initializing consumer: {e}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
