# Pydantic-схемы для валидации событий
from pydantic import BaseModel, conint
from typing import Optional, Any, Dict


class EventSchema(BaseModel):
    product_id: Optional[str]
    event_datetime: Optional[str]
    client_id: Optional[int]
    event_name: Optional[str]
    inserted_dt: Optional[int]
    sid: Optional[conint(strict=True)]
    r: Optional[conint(strict=True)]

    # Дополнительные поля
    additional_fields: Optional[Dict[str, Any]] = {}

    class Config:
        extra = "allow"  # позволяет пропускать все прочие поля, которые мы не описали явно
