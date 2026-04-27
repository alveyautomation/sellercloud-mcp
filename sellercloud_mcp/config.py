"""Configuration for the SellerCloud MCP server.

All settings come from environment variables. Nothing is persisted to disk
and nothing is logged. See `.env.example` for the full list of supported
variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _str(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _optional_int(name: str) -> Optional[int]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the MCP server."""

    api_url: str
    username: str
    password: str
    default_company_id: Optional[int]
    http_timeout: int
    max_retries: int

    @classmethod
    def from_env(cls) -> "Settings":
        api_url = _str("SELLERCLOUD_API_URL")
        username = _str("SELLERCLOUD_USERNAME")
        password = _str("SELLERCLOUD_PASSWORD")

        missing = [
            name
            for name, value in [
                ("SELLERCLOUD_API_URL", api_url),
                ("SELLERCLOUD_USERNAME", username),
                ("SELLERCLOUD_PASSWORD", password),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
                + ". See .env.example for the full list."
            )

        # Trailing slash is required for path joining
        assert api_url is not None
        if not api_url.endswith("/"):
            api_url = api_url + "/"

        return cls(
            api_url=api_url,
            username=username,  # type: ignore[arg-type]
            password=password,  # type: ignore[arg-type]
            default_company_id=_optional_int("SELLERCLOUD_DEFAULT_COMPANY_ID"),
            http_timeout=_int("SELLERCLOUD_HTTP_TIMEOUT", 60),
            max_retries=_int("SELLERCLOUD_MAX_RETRIES", 3),
        )
