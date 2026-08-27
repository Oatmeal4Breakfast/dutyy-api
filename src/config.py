import secrets
from functools import lru_cache
from enum import StrEnum, auto
from urllib.parse import quote_plus
from pydantic import Field, AnyHttpUrl
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

    postgres_user: str = Field(default=...)
    postgres_host: str = Field(default=...)
    postgres_db: str = Field(default=...)
    postgres_password: str = Field(default=...)
    frontend_url: str = Field(default=...)
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
    token_ttl: timedelta = Field(default=...)
    secret: str = Field(default=...)
    jwt_ttl: timedelta = Field(default_factory=lambda: timedelta(minutes=15))
    algorithm: str = "HS256"
    fake_password: str = Field(default_factory=lambda: secrets.token_hex(16))


class EmailServiceConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, env_file_encoding="utf-8", extra="ignore"
    )
    resend_api_key: str = Field(default=...)
    sender_email: str = Field(default=...)


class DeviceAuthConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="DEVICE_AUTH_",
    )

    max_attempts: int = Field(default=3)
    verification_base_uri: AnyHttpUrl = Field(default=...)
    interval: int = Field(default=5)


@lru_cache
def get_config() -> Config:
    return Config()


@lru_cache
def get_auth_service_config() -> AuthServiceConfig:
    return AuthServiceConfig()


@lru_cache
def get_email_service_config() -> EmailServiceConfig:
    return EmailServiceConfig()


@lru_cache
def get_device_auth_config() -> DeviceAuthConfig:
    return DeviceAuthConfig()
