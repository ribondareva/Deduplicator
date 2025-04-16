#!/bin/bash

echo "Waiting for Kafka brokers..."
until nc -z kafka1 9093; do sleep 2; done
until nc -z kafka2 9094; do sleep 2; done
until nc -z kafka3 9095; do sleep 2; done
echo "All Kafka brokers are ready!"