#!/bin/bash
set -e

host="$DB_HOST"
port="$DB_PORT"
user="$DB_USER"
password="$DB_PASSWORD"
db="$DB_NAME"

echo "Ожидание PostgreSQL ($host:$port)..."

until PGPASSWORD="$password" psql -h "$host" -p "$port" -U "$user" -d "$db" -c '\q' >/dev/null 2>&1; do
  echo "PostgreSQL недоступен, ждем..."
  sleep 2
done

echo "PostgreSQL доступен!"

echo "Ожидание Redis Cluster..."
while ! python3 -c "
import socket, sys
nodes = '${REDIS_NODES}'.split(',')
for node in nodes:
    try:
        host, port = node.split(':')
        socket.create_connection((host, int(port)), timeout=5)
    except:
        sys.exit(1)
sys.exit(0)
"; do
    sleep 5
done
echo "Redis Cluster доступен!"