import logging

from fastapi import APIRouter, HTTPException
from api.schemas import EventSchema
from app.deduplicator.bloom_filter import get_deduplicator
from deduplicator.producer import send_event_to_kafka

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/event")
async def process_event(event: EventSchema):
    item_id = event.product_id
    async with get_deduplicator() as deduplicator:
        try:
            if not item_id:
                logger.warning("Missing product_id in event: %s", event)
                raise HTTPException(status_code=400, detail="Missing product_id")

            is_unique = await deduplicator.is_unique(item_id)

            if is_unique:
                logger.info("Event is unique, sending to Kafka: %s", event)
                await send_event_to_kafka(event)
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
