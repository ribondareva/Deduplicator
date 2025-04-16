import asyncio

from aiokafka import AIOKafkaProducer
from api.schemas import EventSchema

from config import settings

producer: AIOKafkaProducer = None

MAX_RETRIES = 5


async def init_kafka_producer():
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    )
    await producer.start()

    for attempt in range(MAX_RETRIES):
        try:
            partitions = await producer.partitions_for(settings.KAFKA_TOPIC_NAME)
            if partitions:
                print(f"Kafka topic '{settings.KAFKA_TOPIC_NAME}' is available with partitions: {partitions}")
                return
            else:
                print(f"Topic exists but has no partitions yet (attempt {attempt + 1})")
        except Exception as e:
            print(
                f"Waiting for Kafka topic '{settings.KAFKA_TOPIC_NAME}' to become available (attempt {attempt + 1})")
            print(f"Error: {e}")

        await asyncio.sleep(3)

    raise RuntimeError(f"Kafka topic '{settings.KAFKA_TOPIC_NAME}' not available after {MAX_RETRIES} attempts.")


async def close_kafka_producer():
    global producer
    if producer:
        await producer.stop()


async def send_event_to_kafka(event: EventSchema):
    global producer
    if not producer:
        raise RuntimeError("Kafka producer is not initialized")
    await producer.send_and_wait(settings.KAFKA_TOPIC_NAME, event.model_dump_json().encode("utf-8"))
