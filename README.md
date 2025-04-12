# 🧹 Микросервис Дедупликатор

Микросервис для дедупликации продуктовых событий с использованием FastAPI, Kafka, RedisBloom и PostgreSQL. SQLAlchemy используется только для описания моделей и генерации миграций через Alembic. Взаимодействие с БД реализовано напрямую через async.

## 📌 Описание

Этот сервис принимает входящие события через HTTP, отправляет их в Kafka, где они обрабатываются consumer-ом. Затем происходит проверка на уникальность с помощью Redis и фильтра Блума, после чего уникальные события сохраняются в PostgreSQL.

## 🚀 Стек технологий

- **Python 3.11+**
- **FastAPI**
- **Apache Kafka**
- **RedisBloom**
- **PostgreSQL**
- **Docker + Docker Compose**
- **Poetry** для управления зависимостями
- **Alembic** для применения миграций


## ⚙️ Переменные окружения

Создайте файл `.env` внутри `app/`:

```env
REDIS_HOST=redis
REDIS_PORT=6379

DB_HOST=postgres
DB_PORT=5432
DB_NAME=events
DB_USER=postgres
DB_PASSWORD=password

KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TOPIC_NAME=events

APP_ENV=development
```

## ⚙️ Запуск
- Клонируйте репозиторий на локальную машину
```
git clone https://github.com/ribondareva/Deduplicator
```
- Сделайте папку app as sources root
- Установите Docker и Docker Compose
- Соберите и запустите контейнеры:
```
docker-compose up --build
```
- API будет доступен на http://localhost:8000/docs
