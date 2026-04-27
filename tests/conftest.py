"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
from typing import Iterator
from unittest.mock import MagicMock

import pytest

from sellercloud_mcp.client import SellerCloudClient
from tests.fixtures import SAMPLE_TOKEN_RESPONSE


@pytest.fixture(autouse=True)
def _reset_server_singletons():
    """Each test starts with a fresh server-module singleton state.

    The MCP server lazily caches a Settings + SellerCloudClient instance.
    Reset between tests so env-var changes take effect and one test's
    mock client doesn't leak into the next.
    """
    from sellercloud_mcp import server as srv

    srv._settings = None
    srv._client = None
    yield
    srv._settings = None
    srv._client = None


@pytest.fixture
def env_credentials(monkeypatch) -> Iterator[None]:
    monkeypatch.setenv(
        "SELLERCLOUD_API_URL", "https://sandbox.api.sellercloud.example/rest/"
    )
    monkeypatch.setenv("SELLERCLOUD_USERNAME", "sandbox-user")
    monkeypatch.setenv("SELLERCLOUD_PASSWORD", "sandbox-pass")
    monkeypatch.setenv("SELLERCLOUD_DEFAULT_COMPANY_ID", "9001")
    yield


@pytest.fixture
def mock_session() -> MagicMock:
    """A mocked `requests.Session` that returns canned token + JSON bodies."""
    session = MagicMock()

    def post(url, json=None, headers=None, timeout=None):
        if url.endswith("/api/token"):
            resp = MagicMock()
            resp.status_code = 200
            resp.ok = True
            resp.json.return_value = SAMPLE_TOKEN_RESPONSE
            return resp
        raise AssertionError(f"Unexpected POST: {url}")

    session.post.side_effect = post
    return session


@pytest.fixture
def client(mock_session) -> SellerCloudClient:
    return SellerCloudClient(
        base_url="https://sandbox.api.sellercloud.example/rest/",
        username="sandbox-user",
        password="sandbox-pass",
        timeout=10,
        max_retries=2,
        session=mock_session,
    )


def _integration_enabled() -> bool:
    return os.environ.get("SELLERCLOUD_INTEGRATION_TESTS") == "1"


integration_only = pytest.mark.skipif(
    not _integration_enabled(),
    reason="Integration tests require SELLERCLOUD_INTEGRATION_TESTS=1 + valid creds",
)
