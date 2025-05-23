FROM python:3.11-slim

# Устанавливаем зависимости ОС
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    netcat-openbsd \
    postgresql-client \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry
ENV POETRY_VERSION=1.6.1
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Рабочая директория
WORKDIR /app

# Копируем зависимости
COPY pyproject.toml poetry.lock ./
COPY init-cluster.sh start-consumer.sh wait_for_kafka.sh ./

# Устанавливаем зависимости через Poetry
RUN poetry config virtualenvs.create false \
 && poetry install --no-root --no-interaction --no-ansi --with dev

# Копируем всё остальное
COPY . .

# Даем права на выполнение
RUN chmod +x init-cluster.sh start-consumer.sh wait_for_kafka.sh

# Открываем порт
EXPOSE 8000