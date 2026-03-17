from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    service_name: str = "users"

    database_url: str = "postgresql+asyncpg://app:app@postgres:5432/app"

    jwt_secret_key: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expires_seconds: int = 3600

    admin_email: str | None = None
    admin_password: str | None = None


settings = Settings()
