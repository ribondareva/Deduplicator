import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Any

import asyncpg
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from app.api.schemas import EventSchema
from config import settings

Base = declarative_base()
logger = logging.getLogger(__name__)


def datetime_converter(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError("Object of type %s is not JSON serializable", o.__class__.__name__)


def get_event_hash(event: EventSchema) -> str:
    event_dict = event.dict()
    event_json = json.dumps(event_dict, sort_keys=True, default=datetime_converter)
    return hashlib.md5(event_json.encode()).hexdigest()


class ProductEventDB(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String, index=True)
    event_type = Column(String)
    client_id = Column(String, index=True)
    event_datetime = Column(DateTime(timezone=True), nullable=True)
    inserted_dt = Column(DateTime(timezone=True), nullable=True)
    sid = Column(String)
    r = Column(String)
    event_data = Column(JSONB)
    event_hash = Column(String, index=True, unique=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def init_db(self):
        self.pool = await asyncpg.create_pool(
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            min_size=50,
            max_size=300,
        )

    async def close_db(self):
        if self.pool:
            await self.pool.close()

    async def insert_event(self, event: EventSchema, event_hash: str) -> None:
        """Добавление уникального события в таблицу events"""
        async with self.pool.acquire() as conn:
            logger.info("Added to DB")
            await conn.execute(
                """
                INSERT INTO events (
                    event_id, event_type, client_id, event_datetime, inserted_dt,
                    sid, r, event_data, event_hash, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                event.product_id,
                event.event_name,
                str(event.client_id) if event.client_id else None,
                event.event_datetime,
                event.inserted_dt,
                event.sid,
                event.r,
                json.dumps(event.dict(), default=str),
                event_hash,
                datetime.utcnow(),
            )

    async def check_event_exists(self, event_hash: str) -> bool:
        """Проверка, существует ли событие с данным event_hash"""
        logger.info("Checking DB for event_hash: %s", event_hash)
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT 1 FROM events WHERE event_hash = $1",
                event_hash
            )
            return result is not None
