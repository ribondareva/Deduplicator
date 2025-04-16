#!/bin/bash

echo "Ожидаем готовности Redis-нод..."
sleep 10

echo "Создаем кластер Redis..."
redis-cli --cluster create \
    redis-node-0:6379 \
    redis-node-1:6379 \
    redis-node-2:6379 \
    redis-node-3:6379 \
    redis-node-4:6379 \
    redis-node-5:6379 \
    --cluster-replicas 1 \
    --cluster-yes
