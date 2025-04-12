# настройки (Redis, Kafka)
from dotenv import load_dotenv
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_BLOOM_KEY: str

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_TOPIC_NAME: str

    APP_ENV: str

    @property
    def SQLALCHEMY_ASYNC_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            path=self.DB_NAME or "",
        )

    class Config:
        env_file = "app/.env"


settings = Settings()
