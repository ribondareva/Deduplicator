#!/bin/bash

# Загрузка .env файла
if [ -f app/.env ]; then
  export $(grep -v '^#' .env | xargs)
else
  echo ".env файл не найден"
  exit 1
fi

# Хост и порт Kafka из переменных окружения
KAFKA_HOST="${KAFKA_BOOTSTRAP_SERVERS%%:*}"
KAFKA_PORT="${KAFKA_BOOTSTRAP_SERVERS##*:}"

MAX_RETRIES=30
RETRY_INTERVAL=5

echo "Ожидание Kafka на $KAFKA_HOST:$KAFKA_PORT..."

for i in $(seq 1 $MAX_RETRIES); do
    nc -z $KAFKA_HOST $KAFKA_PORT && echo "Kafka доступна!" && exit 0
    echo "Попытка $i/$MAX_RETRIES: Kafka не доступна, повтор через $RETRY_INTERVAL секунд..."
    sleep $RETRY_INTERVAL
done

echo "Ошибка: Kafka не доступна после $MAX_RETRIES попыток."
exit 1
