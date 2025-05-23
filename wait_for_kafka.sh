#!/bin/bash

echo "Ожидание Kafka брокеров..."
until kafka-broker-api-versions.sh --bootstrap-server kafka1:9093 >/dev/null 2>&1; do
  sleep 2
done

until kafka-broker-api-versions.sh --bootstrap-server kafka2:9094 >/dev/null 2>&1; do
  sleep 2
done

until kafka-broker-api-versions.sh --bootstrap-server kafka3:9095 >/dev/null 2>&1; do
  sleep 2
done

echo "Все Kafka брокеры доступны!"