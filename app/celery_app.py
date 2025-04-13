from celery import Celery
from celery.schedules import crontab

from app.config import settings

# Настройка Celery
celery_app = Celery(
    "deduplication_service",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
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
