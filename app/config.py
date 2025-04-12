# настройки (Redis, Kafka)
from dotenv import load_dotenv
from hashlib import sha256
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: int

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_TOPIC_NAME: str

    APP_ENV: str

    @property
    def REDIS_BLOOM_KEY(self) -> str:
        base = f"{self.APP_ENV}:{self.DB_NAME}:{self.KAFKA_TOPIC_NAME}"
        hashed_key = sha256(base.encode()).hexdigest()
        return f"bloom:{hashed_key}"

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
        env_file = ".env"


settings = Settings()
