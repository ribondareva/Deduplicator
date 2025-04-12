#!/bin/bash
set -e

host="postgres"
port="5432"
user="postgres"
password="password"
db="events"

echo "Ожидание PostgreSQL ($host:$port)..."

# Ожидание доступности PostgreSQL
until PGPASSWORD="$password" psql -h "$host" -p "$port" -U "$user" -d "$db" -c '\q' >/dev/null 2>&1; do
  echo "PostgreSQL недоступен, ждем..."
  sleep 2
done

echo "PostgreSQL доступен!"

# Проверка наличия alembic.ini
if [ -f "/app/alembic.ini" ]; then
    echo "Применение миграций..."

    # Дополнительная проверка порта базы
    until nc -z -v -w30 "$host" "$port"; do
        echo "Ожидание базы данных..."
        sleep 1
    done

    # Запуск миграций
    poetry run alembic -c /app/alembic.ini upgrade head
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "Миграции успешно применены!"
    else
        echo "Ошибка применения миграций!" >&2
        exit $exit_code
    fi
else
    echo "Файл alembic.ini не найден!" >&2
    exit 1
fi
