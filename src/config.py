import secrets
from enum import StrEnum, auto
from urllib.parse import quote_plus
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import timedelta


class ENV(StrEnum):
    DEVELOPMENT = auto()
    STAGING = auto()
    PRODUCTION = auto()


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, env_file_encoding="utf-8", extra="ignore"
    )

    postgres_user: str
    postgres_host: str
    postgres_db: str
    postgres_password: str
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    max_overflow: int = Field(default=10)
    pool_size: int = Field(default=5)

    env: ENV = Field(default=ENV.DEVELOPMENT)

    @property
    def uri(self) -> str:
        return f"postgresql+psycopg://{self.postgres_user}:{quote_plus(self.postgres_password)}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


class AuthServiceConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    secret: str = Field(default_factory=lambda: secrets.token_hex(16))
    expire_time: timedelta = Field(default_factory=lambda: timedelta(minutes=15))


def get_config() -> Config:
    return Config()


def get_auth_service_config() -> AuthServiceConfig:
    return AuthServiceConfig()
