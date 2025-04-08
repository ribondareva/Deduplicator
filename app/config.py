# настройки (Redis, Kafka)
import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # kafka_bootstrap_servers: str
    # kafka_topic_name: str

    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_BLOOM_KEY: str = os.getenv("REDIS_BLOOM_KEY", "product-events-bloom")

    app_env: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
