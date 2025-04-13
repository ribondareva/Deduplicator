# Удаление из базы данных событий, которым больше 7 дней
import asyncio

from celery import Celery
from deduplicator.db import Database
from datetime import datetime

app = Celery('tasks', broker='redis://redis:6379/1')


@app.task
def purge_old_events():
    """Задача для очистки старых событий из базы данных."""
    asyncio.run(_purge_old_events())


async def _purge_old_events():
    db = Database()
    await db.init_db()
    async with db.pool.acquire() as conn:
        await conn.execute("DELETE FROM events WHERE created_at < NOW() - INTERVAL '7 days'")
    await db.close_db()
    print(f"Old events purged at {datetime.utcnow()}")
