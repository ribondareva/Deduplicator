import logging

from fastapi import FastAPI
from api.endpoints import router as api_router
from deduplicator.bloom_filter import Deduplicator
from deduplicator.producer import init_kafka_producer, close_kafka_producer
from tasks import purge_old_events
from logger_config import setup_logger

setup_logger()

logger = logging.getLogger(__name__)
main_app = FastAPI(title="Deduplication Service")

# Глобальные объекты для Redis и Kafka, которые будут использоваться во всем приложении
redis_connection = None
kafka_producer = None
deduplicator = Deduplicator()


async def init_services():
    """ Инициализация Redis и Kafka с ожиданием готовности. """
    global redis_connection, kafka_producer

    logger.info("Starting up: initializing Redis and Kafka")

    # Инициализируем Redis
    await deduplicator.init_redis()

    # Получаем ссылку на соединение Redis после инициализации
    redis_connection = deduplicator.redis_connection

    # Проверяем, что Redis готов
    redis_ready = await deduplicator.wait_for_cluster_ready()
    if not redis_ready:
        raise RuntimeError("Redis cluster is not ready")

    # Инициализируем Kafka
    kafka_producer = await init_kafka_producer()

    # Запускаем задачу purge_old_events через 24 часа (3600 * 24 секунд)
    purge_old_events.apply_async(countdown=3600 * 24)

    logger.info("Startup completed successfully")


async def shutdown_services():
    """ Ожидаем, пока все сервисы будут корректно завершены. """
    logger.info("Shutting down: closing Redis and Kafka")

    # Закрываем соединения с Redis и Kafka
    if redis_connection:
        await deduplicator.close()
    if kafka_producer:
        await close_kafka_producer()


@main_app.on_event("startup")
async def startup():
    """ Обработчик старта. Ожидаем, пока Redis и Kafka не будут готовы. """
    try:
        await init_services()
        main_app.state.deduplicator = deduplicator  # type: ignore[attr-defined]
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


@main_app.on_event("shutdown")
async def shutdown():
    """ Обработчик завершения работы. Закрытие Redis и Kafka. """
    await shutdown_services()


main_app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:main_app", host="0.0.0.0", port=8000)
