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