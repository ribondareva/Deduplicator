from fastapi import APIRouter, HTTPException
from api.schemas import EventSchema
from deduplicator.bloom_filter import Deduplicator
from deduplicator.producer import send_event_to_kafka

router = APIRouter()

deduplicator = Deduplicator()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.on_event("startup")
async def startup():
    await deduplicator.init_redis()


@router.post("/event")
async def process_event(event: EventSchema):
    item_id = event.product_id
    if not item_id:
        raise HTTPException(status_code=400, detail="Missing product_id")

    is_unique = await deduplicator.is_unique(item_id)

    if is_unique:
        await deduplicator.add_to_bloom(item_id)
        await send_event_to_kafka(event)
        return {"message": "Event is unique and sent to Kafka", "item_id": item_id}
    else:
        raise HTTPException(status_code=400, detail=f"Event with item_id {item_id} is not unique")
