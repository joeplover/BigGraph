import pytest

from config.settings import Settings


def test_production_requires_jwt_secret_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    settings = Settings()

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        settings.validate_for_runtime()


def test_development_allows_local_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    settings = Settings()

    settings.validate_for_runtime()
