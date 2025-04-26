import asyncio
import logging

from celery_app import celery_app
from deduplicator.db import Database
from datetime import datetime

logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.purge_old_events')
def purge_old_events():
    """Задача для очистки старых событий из базы данных."""
    logger.info("Starting purge...")
    asyncio.run(_purge_old_events())
    logger.info("Purge completed at %s", datetime.utcnow())


async def _purge_old_events():
    """Удаление из базы данных событий, которым больше 7 дней"""
    try:
        db = Database()
        await db.init_db()
        async with db.pool.acquire() as conn:
            deleted = await conn.execute("DELETE FROM events WHERE created_at < NOW() - INTERVAL '7 days'")
            await db.close_db()
            logger.info("Deleted %s old events", deleted)
    except Exception as e:
        logger.error("Purge failed: %s", str(e))
