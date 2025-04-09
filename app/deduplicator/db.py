import json
import uuid
from datetime import datetime

import asyncpg
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base

from app.api.schemas import EventSchema
from config import settings

Base = declarative_base()


class ProductEventDB(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String, index=True)
    event_type = Column(String)
    client_id = Column(String, index=True)
    event_datetime = Column(DateTime, nullable=True)
    inserted_dt = Column(DateTime, nullable=True)
    sid = Column(String)
    r = Column(String)
    event_data = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


class Database:
    def __init__(self):
        self.connection: asyncpg.Connection | None = None

    async def init_db(self):
        """Инициализация подключения к базе данных PostgreSQL"""
        self.connection = await asyncpg.connect(
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
        )

    async def close_db(self):
        """Закрытие подключения к базе данных"""
        if self.connection:
            await self.connection.close()

    async def insert_event(self, event: EventSchema):
        """Добавление уникального события в таблицу events"""

        event_dict = event.dict()
        product_id = event_dict.get("product_id")

        query = """
        INSERT INTO events (
            event_id, event_type, client_id, event_datetime, inserted_dt, sid, r, event_data, created_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9
        )
        """

        await self.connection.execute(
            query,
            product_id,
            event.event_name,
            str(event.client_id) if event.client_id else None,
            event.event_datetime,
            event.inserted_dt,
            event.sid,
            event.r,
            json.dumps(event_dict),
            datetime.utcnow(),
        )

    async def check_event_exists(self, item_id: str) -> bool:
        """Проверка, существует ли событие с данным product_id"""
        query = "SELECT 1 FROM events WHERE event_id = $1 LIMIT 1"
        result = await self.connection.fetch(query, item_id)
        return bool(result)
