import asyncio

from fastapi import FastAPI
from api.endpoints import router as api_router
from logger_config import setup_logger

setup_logger()

from deduplicator.producer import init_kafka_producer, close_kafka_producer
from tasks import purge_old_events

main_app = FastAPI(title="Deduplication Service")

main_app.include_router(api_router)


@main_app.on_event("startup")
async def startup():
    await asyncio.sleep(5)
    await init_kafka_producer()
    # Запускаем задачу purge_old_events через 24 часа (3600 * 24 секунд)
    purge_old_events.apply_async(countdown=3600 * 24)


@main_app.on_event("shutdown")
async def shutdown():
    await close_kafka_producer()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:main_app", host="0.0.0.0", port=8000, reload=True)
