import asyncio
import json
import logging
from datetime import datetime

from aiokafka import AIOKafkaProducer
from api.schemas import EventSchema

from config import settings

logger = logging.getLogger(__name__)

producer: AIOKafkaProducer = None

MAX_RETRIES = 5


# Функция для сериализации данных, чтобы обрабатывать datetime
def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()  # Преобразовываем datetime в строку
    raise TypeError(f"Type {type(obj)} not serializable")


# Функция сериализации событий
def serialize_event(event: EventSchema) -> str:
    return json.dumps(event.dict(), default=json_serializer, sort_keys=True)


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
    try:
        event_dict = event.dict()
        logger.info("Event dict before serialization: %s", event_dict)

        message = serialize_event(event)
        logger.info("Serialized event to send to Kafka: %s", message)

        await producer.send_and_wait(settings.KAFKA_TOPIC_NAME, message.encode("utf-8"))
        logger.info("Event sent to Kafka: %s", message)
    except Exception as e:
        logger.error("Failed to send event to Kafka: %s", e)
        raise
