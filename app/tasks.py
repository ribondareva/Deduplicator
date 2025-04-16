# Удаление из базы данных событий, которым больше 7 дней
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
    logger.info(f"Purge completed at {datetime.utcnow()}")


async def _purge_old_events():
    try:
        db = Database()
        await db.init_db()
        async with db.pool.acquire() as conn:
            deleted = await conn.execute("DELETE FROM events WHERE created_at < NOW() - INTERVAL '7 days'")
            await db.close_db()
            logger.info(f"Deleted {deleted} old events")
    except Exception as e:
        logger.error(f"Purge failed: {str(e)}")
