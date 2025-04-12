from fastapi import APIRouter, HTTPException, Depends
from api.schemas import EventSchema
from deduplicator.bloom_filter import Deduplicator, get_deduplicator
from deduplicator.producer import send_event_to_kafka

router = APIRouter()

# deduplicator = Deduplicator()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/event")
async def process_event(event: EventSchema, deduplicator: Deduplicator = Depends(get_deduplicator)):
    item_id = event.product_id
    if not item_id:
        raise HTTPException(status_code=400, detail="Missing product_id")

    is_unique = await deduplicator.is_unique(item_id)

    if is_unique:
        # await deduplicator.add_to_bloom(item_id)
        await send_event_to_kafka(event)
        return {"message": "Event is unique and sent to Kafka", "item_id": item_id}
    else:
        raise HTTPException(status_code=400, detail=f"Event with item_id {item_id} is not unique")
