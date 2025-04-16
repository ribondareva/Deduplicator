FROM python:3.12-slim

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
COPY start-consumer.sh init-cluster.sh ./

# Устанавливаем зависимости через Poetry
RUN poetry config virtualenvs.create false \
 && poetry install --no-root --no-interaction --no-ansi

# Копируем всё остальное
COPY . .

# Даем права на выполнение
RUN chmod +x start-consumer.sh init-cluster.sh

# Открываем порт
EXPOSE 8000