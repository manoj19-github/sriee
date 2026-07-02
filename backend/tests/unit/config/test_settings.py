from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError

from jarvis.config.settings import (
    AppEnvironment,
    Settings,
    SettingsLoadError,
    load_settings,
    loadSettings,
)


def valid_values() -> dict[str, object]:
    return {
        "DB_HOST": "db.internal",
        "DB_PORT": 5432,
        "DB_NAME": "jarvis_test",
        "DB_USER": "jarvis_test",
        "DB_PASSWORD": "database-password",
        "DEFAULT_SCHEMA": "jarvis",
        "JWT_ACCESS_SECRET": "a" * 32,
        "JWT_REFRESH_SECRET": "b" * 32,
    }


def test_module_import_does_not_load_environment() -> None:
    module = importlib.import_module("jarvis.config.settings")

    assert not hasattr(module, "settings")


def test_loads_typed_immutable_settings_from_explicit_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEBUG", "an-unrelated-host-value")
    settings = loadSettings(overrides=valid_values())

    assert settings.db_port == 5432
    assert settings.default_schema == "jarvis"
    assert settings.app_environment is AppEnvironment.DEVELOPMENT
    with pytest.raises(ValidationError):
        settings.port = 8000


def test_loads_dotenv_and_environment_takes_precedence(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in valid_values().items()),
        encoding="utf-8",
    )
    monkeypatch.setenv("DB_NAME", "from_environment")

    settings = load_settings(env_file=env_file)

    assert settings.db_name == "from_environment"


@pytest.mark.parametrize("environment", ["developement", "prod", "local"])
def test_rejects_unknown_environment_without_echoing_input(environment: str) -> None:
    values = valid_values() | {"NODE_ENV": environment}

    with pytest.raises(SettingsLoadError) as captured:
        load_settings(overrides=values)

    assert environment not in str(captured.value)
    assert "NODE_ENV" in str(captured.value)


def test_rejects_unsafe_production_configuration() -> None:
    values = valid_values() | {
        "JARVIS_ENV": "production",
        "JARVIS_DEBUG": True,
    }

    with pytest.raises(SettingsLoadError):
        load_settings(overrides=values)


def test_requires_isolated_jarvis_schema() -> None:
    values = valid_values() | {"DEFAULT_SCHEMA": "public"}

    with pytest.raises(SettingsLoadError):
        load_settings(overrides=values)


def test_rejects_shared_jwt_secret() -> None:
    values = valid_values() | {
        "JWT_ACCESS_SECRET": "s" * 32,
        "JWT_REFRESH_SECRET": "s" * 32,
    }

    with pytest.raises(SettingsLoadError):
        load_settings(overrides=values)


def test_safe_diagnostics_and_fingerprint_never_contain_secrets() -> None:
    values = valid_values()
    settings = load_settings(overrides=values)

    diagnostics = settings.safe_diagnostics()
    fingerprint = settings.safe_fingerprint()
    serialized = repr(diagnostics) + fingerprint

    assert diagnostics["database_configured"] is True
    assert diagnostics["database_schema"] == "jarvis"
    assert len(fingerprint) == 16
    assert str(values["DB_PASSWORD"]) not in serialized
    assert str(values["JWT_ACCESS_SECRET"]) not in serialized
    assert settings.db_host not in serialized
    assert settings.db_user not in serialized


def test_sanitized_error_does_not_expose_secret_value() -> None:
    secret = "too-short-and-sensitive"
    values = valid_values() | {"JWT_ACCESS_SECRET": secret}

    with pytest.raises(SettingsLoadError) as captured:
        load_settings(overrides=values)

    assert secret not in str(captured.value)
