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

echo "Ожидание Redis Cluster..."
while ! python3 -c "
import socket, sys
for node in ['redis-node-0', 'redis-node-1', 'redis-node-2', 'redis-node-3', 'redis-node-4', 'redis-node-5']:
    try:
        socket.create_connection((node, 6379), timeout=5)
    except:
        sys.exit(1)
sys.exit(0)
"; do
    sleep 5
done
echo "Redis Cluster доступен!"