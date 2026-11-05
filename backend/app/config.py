"""Shared process settings; container values are supplied by Compose."""
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )
    app_env: str = "development"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_user: str = "campus"
    postgres_password: SecretStr = SecretStr("campus_dev_password")
    postgres_db: str = "campus"
    database_url: SecretStr | None = None
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    worker_poll_interval_seconds: float = Field(default=1.0, gt=0)
    health_timeout_seconds: float = Field(default=3.0, gt=0)
    event_stream: str = Field(default="campus:events", min_length=1)
    consumer_retry_idle_ms: int = Field(default=1000, ge=100)
    consumer_reconcile_interval_seconds: float = Field(default=3.0, gt=0)

    @field_validator("database_url", mode="before")
    @classmethod
    def empty_database_url(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("database_url")
    @classmethod
    def require_asyncpg(cls, value: SecretStr | None) -> SecretStr | None:
        if value and make_url(value.get_secret_value()).drivername != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        return value

    @property
    def sqlalchemy_url(self) -> URL:
        if self.database_url:
            return make_url(self.database_url.get_secret_value())
        return URL.create(
            "postgresql+asyncpg", username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host, port=self.postgres_port, database=self.postgres_db,
        )
