import logging
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from api.schemas import EventSchema
from deduplicator.producer import send_event_to_kafka

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/health-redis")
async def health_check_redis(request: Request):
    deduplicator = request.app.state.deduplicator
    redis_ready = await deduplicator.wait_for_cluster_ready()
    if redis_ready:
        return JSONResponse(status_code=200, content={"status": "Redis Cluster is ready"})
    else:
        return JSONResponse(status_code=500, content={"status": "Redis Cluster is not ready"})


@router.post("/event")
async def process_event(event: EventSchema, request: Request):
    deduplicator = request.app.state.deduplicator
    item_id = event.product_id
    total_start = time.monotonic()  # замер всей обработки
    try:
        if not item_id:
            logger.warning("Missing product_id in event: %s", event)
            raise HTTPException(status_code=400, detail="Missing product_id")

        # Redis Bloom check
        redis_start = time.monotonic()
        is_unique = await deduplicator.is_unique(item_id)
        redis_duration = time.monotonic() - redis_start
        logger.info(f"Redis Bloom check took {redis_duration:.3f}s")

        if is_unique:
            # Kafka step
            kafka_start = time.monotonic()
            logger.info("Event is unique, sending to Kafka: %s", event)
            await send_event_to_kafka(event)
            kafka_duration = time.monotonic() - kafka_start
            logger.info(f"Kafka send took {kafka_duration:.3f}s")

            # Сразу добавляем в Redis Bloom, чтобы предотвратить повторное попадание
            await deduplicator.add_to_bloom(item_id)

            total_duration = time.monotonic() - total_start
            logger.info(f"Total /event handling took {total_duration:.3f}s")

            return {"message": "Event is unique and sent to Kafka", "item_id": item_id}
        else:
            logger.warning("Event is not unique: %s", event)
            raise HTTPException(status_code=400, detail=f"Event with item_id {item_id} is not unique")
    except RuntimeError as e:
        logger.error("Redis initialization or connection error: %s", str(e))
        raise HTTPException(status_code=500, detail="Error with Redis connection")
    except Exception as e:
        logger.error("Error processing event: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
