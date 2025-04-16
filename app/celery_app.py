from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "deduplication_service",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)
celery_app.conf.beat_schedule = {
    'purge-old-events-every-day': {
        'task': 'app.tasks.purge_old_events',
        'schedule': crontab(minute=0, hour=0),  # Задача будет запускаться каждый день в полночь
    },
}
celery_app.conf.timezone = 'UTC'

# Дополнительная конфигурация
celery_app.conf.update(
    task_routes={
        'app.tasks.purge_old_events': {'queue': 'default'},
    }
)
celery_app.autodiscover_tasks(['app.tasks'], force=True)
