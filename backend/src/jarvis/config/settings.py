"""Explicit, immutable, and secret-safe JARVIS configuration loading."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class SettingsLoadError(RuntimeError):
    """A sanitized configuration error safe to show in diagnostics."""


class Settings(BaseSettings):
    """Immutable application settings loaded only by :func:`load_settings`."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        validate_default=True,
    )

    app_name: str = Field(default="jarvis-os", min_length=1, max_length=64)
    app_environment: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        validation_alias=AliasChoices("JARVIS_ENV", "APP_ENV", "NODE_ENV"),
    )
    debug: bool = Field(default=False, validation_alias="JARVIS_DEBUG")
    host: str = Field(default="127.0.0.1", validation_alias="HOST")
    port: int = Field(default=5000, ge=1, le=65535, validation_alias="PORT")
    log_dir: Path = Field(default=Path("logs"), validation_alias="LOG_DIR")

    db_host: str = Field(min_length=1, validation_alias="DB_HOST")
    db_port: int = Field(default=5432, ge=1, le=65535, validation_alias="DB_PORT")
    db_name: str = Field(min_length=1, validation_alias="DB_NAME")
    db_user: str = Field(min_length=1, validation_alias="DB_USER")
    db_password: SecretStr = Field(min_length=8, validation_alias="DB_PASSWORD")
    default_schema: str = Field(default="jarvis", validation_alias="DEFAULT_SCHEMA")

    redis_host: str | None = Field(default=None, validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, ge=1, le=65535, validation_alias="REDIS_PORT")
    redis_password: SecretStr | None = Field(
        default=None,
        validation_alias="REDIS_PASSWORD",
    )

    jwt_access_secret: SecretStr = Field(
        min_length=32,
        validation_alias="JWT_ACCESS_SECRET",
    )
    jwt_refresh_secret: SecretStr = Field(
        min_length=32,
        validation_alias="JWT_REFRESH_SECRET",
    )

    @field_validator("host", "db_host", "db_name", "db_user", mode="before")
    @classmethod
    def strip_required_text(cls, value: Any) -> Any:
        """Normalize surrounding whitespace without coercing non-string values."""

        return value.strip() if isinstance(value, str) else value

    @field_validator("log_dir", mode="before")
    @classmethod
    def normalize_log_dir(cls, value: Any) -> Any:
        """Accept the common ``LOG_DIR = path`` form without retaining spaces."""

        return value.strip() if isinstance(value, str) else value

    @field_validator("default_schema")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        """Restrict JARVIS to its isolated PostgreSQL schema."""

        normalized = value.strip().lower()
        if normalized != "jarvis":
            raise ValueError("DEFAULT_SCHEMA must be 'jarvis'")
        return normalized

    @model_validator(mode="after")
    def reject_unsafe_configuration(self) -> Settings:
        """Reject combinations that are unsafe outside local development."""

        if self.jwt_access_secret.get_secret_value() == self.jwt_refresh_secret.get_secret_value():
            raise ValueError("access and refresh JWT secrets must be different")

        if self.app_environment in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
            if self.debug:
                raise ValueError("DEBUG must be disabled in staging and production")
            if self.host not in {"127.0.0.1", "::1", "localhost"}:
                raise ValueError("non-loopback HOST requires a separately reviewed remote mode")
            if self.redis_host and self.redis_password is None:
                raise ValueError("REDIS_PASSWORD is required outside local development")

        return self

    def safe_diagnostics(self) -> dict[str, Any]:
        """Return useful configuration facts without paths, hosts, users, or secrets."""

        return {
            "app_name": self.app_name,
            "environment": self.app_environment.value,
            "debug": self.debug,
            "listen_loopback": self.host in {"127.0.0.1", "::1", "localhost"},
            "port": self.port,
            "database_configured": True,
            "database_schema": self.default_schema,
            "redis_configured": self.redis_host is not None,
            "redis_auth_configured": self.redis_password is not None,
            "jwt_access_secret_configured": bool(
                self.jwt_access_secret.get_secret_value()
            ),
            "jwt_refresh_secret_configured": bool(
                self.jwt_refresh_secret.get_secret_value()
            ),
        }

    def safe_fingerprint(self) -> str:
        """Fingerprint only the redacted diagnostic projection."""

        serialized = json.dumps(
            self.safe_diagnostics(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()[:16]


def load_settings(
    *,
    env_file: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Settings:
    """Load and validate settings with a sanitized failure contract.

    No settings object is created at import time. Environment variables remain the
    standard Pydantic Settings source; ``overrides`` is intended for tests and
    explicit programmatic configuration.
    """

    init_values = dict(overrides or {})
    try:
        return Settings(_env_file=env_file, **init_values)
    except ValidationError as error:
        fields = sorted(
            {
                ".".join(str(part) for part in issue["loc"]) or "settings"
                for issue in error.errors(include_url=False, include_input=False)
            }
        )
        raise SettingsLoadError(
            f"Invalid JARVIS configuration for: {', '.join(fields)}"
        ) from None


def loadSettings(
    *,
    env_file: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Settings:
    """Canonical function-map entry point for Global ID 110000."""

    return load_settings(env_file=env_file, overrides=overrides)
