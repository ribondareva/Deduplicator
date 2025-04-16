from aiokafka import AIOKafkaProducer
from api.schemas import EventSchema

from config import settings

producer: AIOKafkaProducer = None


async def init_kafka_producer():
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    )
    await producer.start()
    try:
        # проверка подключения
        partitions = await producer.partitions_for(settings.KAFKA_TOPIC_NAME)
        print(f"Partitions available: {partitions}")
    except Exception as e:
        print(f"Error checking Kafka connection: {e}")


async def close_kafka_producer():
    global producer
    if producer:
        await producer.stop()


async def send_event_to_kafka(event: EventSchema):
    global producer
    if not producer:
        raise RuntimeError("Kafka producer is not initialized")
    await producer.send_and_wait(settings.KAFKA_TOPIC_NAME, event.model_dump_json().encode("utf-8"))

