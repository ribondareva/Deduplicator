# Pydantic-схемы для валидации событий
from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime


class EventSchema(BaseModel):
    product_id: Optional[str]
    event_datetime: Optional[datetime]
    client_id: Optional[int]
    event_name: Optional[str]
    inserted_dt: Optional[datetime]
    sid: Optional[str]
    r: Optional[str]
    additional_fields: Optional[Dict[str, Any]] = {}

    class Config:
        extra = "allow"  # позволяет пропускать все прочие поля
