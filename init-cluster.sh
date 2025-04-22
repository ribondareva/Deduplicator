#!/bin/bash

set -e

echo "Ожидаем готовности Redis-нод..."

# Ждём, пока все ноды ответят на PING
for i in {0..5}; do
  HOST="redis-node-$i"
  until redis-cli -h $HOST -p 6379 ping | grep -q PONG; do
    echo "Ждем $HOST..."
    sleep 2
  done
done

echo "Все Redis-ноды готовы."

# Проверка: не создан ли кластер уже
CLUSTER_INFO=$(redis-cli -h redis-node-0 -p 6379 cluster info 2>/dev/null || echo "")

if echo "$CLUSTER_INFO" | grep -q "cluster_state:ok"; then
  echo "Кластер уже создан. Пропускаем."
  exit 0
fi

echo "Создаем кластер Redis..."

# Создание кластера
redis-cli --cluster create \
  redis-node-0:6379 \
  redis-node-1:6379 \
  redis-node-2:6379 \
  redis-node-3:6379 \
  redis-node-4:6379 \
  redis-node-5:6379 \
  --cluster-replicas 1 \
  --cluster-yes

sleep 3