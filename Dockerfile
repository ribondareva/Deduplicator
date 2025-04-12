FROM python:3.12-slim

# Устанавливаем зависимости для сборки
RUN apt-get update && \
    apt-get install -y curl build-essential netcat-openbsd postgresql-client && \
    apt-get clean

# Устанавливаем Poetry
ENV POETRY_VERSION=1.6.1
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы с зависимостями
COPY pyproject.toml poetry.lock /app/
COPY start-consumer.sh wait_for_kafka.sh /app/

# Устанавливаем зависимости
RUN poetry install --no-root

# Копируем остальной проект
COPY . .

# Делаем стартовый скрипт исполняемым
RUN chmod +x  start-consumer.sh wait_for_kafka.sh

# Открываем порт
EXPOSE 8000
