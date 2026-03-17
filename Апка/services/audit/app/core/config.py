from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    service_name: str = "audit"

    database_url: str = "postgresql+asyncpg://app:app@postgres:5432/app"
    amqp_url: str = "amqp://guest:guest@rabbitmq:5672/"
    events_exchange: str = "events"


settings = Settings()
