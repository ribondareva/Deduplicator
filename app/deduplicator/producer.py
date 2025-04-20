import asyncio
import logging

from aiokafka import AIOKafkaProducer
from api.schemas import EventSchema

from config import settings

logger = logging.getLogger(__name__)

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
                logger.info("Kafka topic '%s' is available with partitions: %s", settings.KAFKA_TOPIC_NAME, partitions)
                return
            else:
                logger.warning("Topic exists but has no partitions yet (attempt %d)", attempt + 1)
        except Exception as e:
            logger.warning(
                "Waiting for Kafka topic '%s' to become available (attempt %d)",
                settings.KAFKA_TOPIC_NAME,
                attempt + 1
            )
            logger.debug("Error while checking topic availability: %s", e)

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
