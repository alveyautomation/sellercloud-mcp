"""Tests for sellercloud_mcp.config.Settings."""

from __future__ import annotations

import pytest

from sellercloud_mcp.config import Settings


def test_settings_from_env_happy_path(monkeypatch):
    monkeypatch.setenv(
        "SELLERCLOUD_API_URL", "https://sandbox.api.sellercloud.example/rest/"
    )
    monkeypatch.setenv("SELLERCLOUD_USERNAME", "sandbox-user")
    monkeypatch.setenv("SELLERCLOUD_PASSWORD", "sandbox-pass")
    monkeypatch.setenv("SELLERCLOUD_DEFAULT_COMPANY_ID", "9001")
    monkeypatch.setenv("SELLERCLOUD_HTTP_TIMEOUT", "45")
    monkeypatch.setenv("SELLERCLOUD_MAX_RETRIES", "5")

    s = Settings.from_env()
    assert s.api_url == "https://sandbox.api.sellercloud.example/rest/"
    assert s.username == "sandbox-user"
    assert s.password == "sandbox-pass"
    assert s.default_company_id == 9001
    assert s.http_timeout == 45
    assert s.max_retries == 5


def test_settings_appends_trailing_slash(monkeypatch):
    monkeypatch.setenv(
        "SELLERCLOUD_API_URL", "https://sandbox.api.sellercloud.example/rest"
    )
    monkeypatch.setenv("SELLERCLOUD_USERNAME", "u")
    monkeypatch.setenv("SELLERCLOUD_PASSWORD", "p")

    s = Settings.from_env()
    assert s.api_url.endswith("/")


def test_settings_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("SELLERCLOUD_API_URL", raising=False)
    monkeypatch.delenv("SELLERCLOUD_USERNAME", raising=False)
    monkeypatch.delenv("SELLERCLOUD_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        Settings.from_env()


def test_settings_optional_company_id_blank(monkeypatch):
    monkeypatch.setenv(
        "SELLERCLOUD_API_URL", "https://sandbox.api.sellercloud.example/rest/"
    )
    monkeypatch.setenv("SELLERCLOUD_USERNAME", "u")
    monkeypatch.setenv("SELLERCLOUD_PASSWORD", "p")
    monkeypatch.setenv("SELLERCLOUD_DEFAULT_COMPANY_ID", "")

    s = Settings.from_env()
    assert s.default_company_id is None


def test_settings_invalid_int(monkeypatch):
    monkeypatch.setenv(
        "SELLERCLOUD_API_URL", "https://sandbox.api.sellercloud.example/rest/"
    )
    monkeypatch.setenv("SELLERCLOUD_USERNAME", "u")
    monkeypatch.setenv("SELLERCLOUD_PASSWORD", "p")
    monkeypatch.setenv("SELLERCLOUD_HTTP_TIMEOUT", "not-a-number")

    with pytest.raises(ValueError, match="must be an integer"):
        Settings.from_env()


def test_settings_default_timeout_and_retries(monkeypatch):
    monkeypatch.setenv(
        "SELLERCLOUD_API_URL", "https://sandbox.api.sellercloud.example/rest/"
    )
    monkeypatch.setenv("SELLERCLOUD_USERNAME", "u")
    monkeypatch.setenv("SELLERCLOUD_PASSWORD", "p")
    monkeypatch.delenv("SELLERCLOUD_HTTP_TIMEOUT", raising=False)
    monkeypatch.delenv("SELLERCLOUD_MAX_RETRIES", raising=False)

    s = Settings.from_env()
    assert s.http_timeout == 60
    assert s.max_retries == 3
