from fastapi import APIRouter
from api.schemas import EventSchema
from deduplicator.bloom_filter import Deduplicator

router = APIRouter()


# Ручка для healthcheck
@router.get("/health")
def health_check():
    return {"status": "ok"}


# Инициализация объекта Deduplicator
deduplicator = Deduplicator()


# Ручка для обработки событий
@router.post("/event")
async def process_event(event: EventSchema):  # Используем EventSchema для валидации
    await deduplicator.init_redis()  # Инициализация Redis (можно переместить в init)

    # Получаем item_id из нового события
    item_id = event.product_id  # Предполагаем, что product_id — это идентификатор события

    is_unique = await deduplicator.is_unique(item_id)

    if is_unique:
        await deduplicator.add_to_bloom(item_id)
        return {"message": "Event added and is unique", "item_id": item_id}
    else:
        return {"message": "Event is not unique", "item_id": item_id}
