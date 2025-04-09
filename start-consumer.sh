#!/bin/bash

# Загрузка .env
if [ -f app/.env ]; then
  export $(grep -v '^#' .env | xargs)
else
  echo ".env файл не найден"
  exit 1
fi

# Функция для ожидания доступности сервиса
wait_for_service() {
  local host=$1
  local port=$2
  local retries=30
  local interval=5
  echo "Ожидание $host:$port..."

  for i in $(seq 1 $retries); do
    (echo > /dev/tcp/$host/$port) &> /dev/null && echo "$host:$port доступен!" && return 0
    echo "Попытка $i/$retries: $host:$port не доступен, повтор через $interval секунд..."
    sleep $interval
  done

  echo "Ошибка: $host:$port не доступен после $retries попыток."
  exit 1
}

# Ожидаем все сервисы
wait_for_service "${KAFKA_BOOTSTRAP_SERVERS%%:*}" "${KAFKA_BOOTSTRAP_SERVERS##*:}"
wait_for_service "$REDIS_HOST" "$REDIS_PORT"
wait_for_service "$DB_HOST" "$DB_PORT"

# Запуск консюмера
echo "Запуск консюмера дедупликатора..."
poetry run python deduplicator/consumer.py
