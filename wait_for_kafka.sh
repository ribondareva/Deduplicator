#!/bin/bash

host="kafka"
port="9092"

echo "Ожидание Kafka ($host:$port)..."

until nc -z -v -w30 "$host" "$port"; do
  echo "Kafka не доступна, повтор через 5 секунд..."
  sleep 5
done

echo "Kafka доступна!"
