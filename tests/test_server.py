"""Tests for the MCP server tool layer.

We exercise the tool functions directly (their underlying Python callable)
to avoid spinning up a real MCP transport in unit tests. The functions
return JSON-encoded envelopes; we decode and assert on shape.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from sellercloud_mcp import server as srv
from tests.fixtures import (
    SAMPLE_CHANNEL_LISTING,
    SAMPLE_CHANNELS,
    SAMPLE_INVENTORY,
    SAMPLE_ORDER_DETAIL,
    SAMPLE_ORDER_LIST_PAGE_1,
    SAMPLE_ORDER_LIST_PAGE_2,
    SAMPLE_PRODUCT,
    SAMPLE_PRODUCT_LIST,
    SANDBOX_COMPANY_PRIMARY,
)


def _call(tool, **kwargs):
    """Invoke a FastMCP-registered tool's underlying Python function."""
    func = getattr(tool, "fn", None) or tool
    return func(**kwargs)


def _decode(envelope: str) -> dict:
    return json.loads(envelope)


def _install_fake_client(monkeypatch, **methods):
    """Replace the lazy-instantiated client with a MagicMock."""
    fake = MagicMock()
    for name, value in methods.items():
        getattr(fake, name).return_value = value if not callable(value) else None
        if callable(value) and not isinstance(value, MagicMock):
            getattr(fake, name).side_effect = value
    monkeypatch.setattr(srv, "_get_client", lambda: fake)
    # Provide a Settings stub so _resolve_company_id has a default to fall back on.
    from sellercloud_mcp.config import Settings

    monkeypatch.setattr(
        srv,
        "_settings",
        Settings(
            api_url="https://sandbox.api.sellercloud.example/rest/",
            username="u",
            password="p",
            default_company_id=SANDBOX_COMPANY_PRIMARY,
            http_timeout=10,
            max_retries=2,
        ),
    )
    return fake


# ---- search_products --------------------------------------------------


def test_search_products_happy(monkeypatch):
    _install_fake_client(monkeypatch, search_products=SAMPLE_PRODUCT_LIST)
    out = _decode(
        _call(
            srv.sellercloud_search_products,
            query="widget",
            company_id=SANDBOX_COMPANY_PRIMARY,
        )
    )
    assert out["ok"] is True
    assert out["data"]["total"] == 2
    assert out["data"]["items"][0]["ID"] == "ACME-WIDGET-001"


def test_search_products_rejects_blank_query(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.sellercloud_search_products, query="   "))
    assert out["ok"] is False
    assert "query is required" in out["error"]


def test_search_products_uses_default_company(monkeypatch):
    fake = _install_fake_client(monkeypatch, search_products=SAMPLE_PRODUCT_LIST)
    _call(srv.sellercloud_search_products, query="widget")
    fake.search_products.assert_called_once()
    assert fake.search_products.call_args.kwargs["company_id"] == SANDBOX_COMPANY_PRIMARY


def test_search_products_clamps_page_size(monkeypatch):
    fake = _install_fake_client(monkeypatch, search_products=SAMPLE_PRODUCT_LIST)
    _call(
        srv.sellercloud_search_products,
        query="x",
        company_id=SANDBOX_COMPANY_PRIMARY,
        page_size=999,
    )
    assert fake.search_products.call_args.kwargs["page_size"] == 50


# ---- get_product -------------------------------------------------------


def test_get_product_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_product=SAMPLE_PRODUCT)
    out = _decode(
        _call(
            srv.sellercloud_get_product,
            sku="ACME-WIDGET-001",
            company_id=SANDBOX_COMPANY_PRIMARY,
        )
    )
    assert out["ok"] is True
    assert out["data"]["ID"] == "ACME-WIDGET-001"


def test_get_product_missing_returns_null(monkeypatch):
    _install_fake_client(monkeypatch, get_product=None)
    out = _decode(
        _call(
            srv.sellercloud_get_product,
            sku="MISSING",
            company_id=SANDBOX_COMPANY_PRIMARY,
        )
    )
    assert out["ok"] is True
    assert out["data"] is None


def test_get_product_blank_sku(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.sellercloud_get_product, sku="   "))
    assert out["ok"] is False


# ---- search_orders -----------------------------------------------------


def test_search_orders_happy(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_orders.return_value = iter(
        SAMPLE_ORDER_LIST_PAGE_1["Items"] + SAMPLE_ORDER_LIST_PAGE_2["Items"]
    )
    out = _decode(
        _call(
            srv.sellercloud_search_orders,
            date_from="2026-04-26",
            date_to="2026-04-26",
            company_id=SANDBOX_COMPANY_PRIMARY,
        )
    )
    assert out["ok"] is True
    assert out["data"]["count"] == 3
    assert {o["OrderID"] for o in out["data"]["orders"]} == {100001, 100002, 100003}


def test_search_orders_rejects_bad_date(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(
        _call(
            srv.sellercloud_search_orders,
            date_from="not-a-date",
            date_to="2026-04-26",
        )
    )
    assert out["ok"] is False
    assert "ISO date" in out["error"]


def test_search_orders_respects_limit(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_orders.return_value = iter(
        SAMPLE_ORDER_LIST_PAGE_1["Items"] + SAMPLE_ORDER_LIST_PAGE_2["Items"]
    )
    out = _decode(
        _call(
            srv.sellercloud_search_orders,
            date_from="2026-04-26",
            date_to="2026-04-26",
            limit=2,
        )
    )
    assert out["data"]["count"] == 2
    assert out["data"]["limit_reached"] is True


# ---- get_order ---------------------------------------------------------


def test_get_order_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_order=SAMPLE_ORDER_DETAIL)
    out = _decode(_call(srv.sellercloud_get_order, order_id=100001))
    assert out["ok"] is True
    assert out["data"]["OrderID"] == 100001


def test_get_order_rejects_non_positive(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.sellercloud_get_order, order_id=0))
    assert out["ok"] is False


# ---- get_inventory -----------------------------------------------------


def test_get_inventory_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_inventory=SAMPLE_INVENTORY)
    out = _decode(
        _call(
            srv.sellercloud_get_inventory,
            sku="ACME-WIDGET-001",
            company_id=SANDBOX_COMPANY_PRIMARY,
        )
    )
    assert out["ok"] is True
    assert out["data"]["InventoryAvailableQty"] == 42


def test_get_inventory_missing(monkeypatch):
    _install_fake_client(monkeypatch, get_inventory=None)
    out = _decode(
        _call(
            srv.sellercloud_get_inventory,
            sku="MISSING-001",
            company_id=SANDBOX_COMPANY_PRIMARY,
        )
    )
    assert out["ok"] is True
    assert out["data"] is None


# ---- list_channels -----------------------------------------------------


def test_list_channels_happy(monkeypatch):
    _install_fake_client(monkeypatch, list_channels=SAMPLE_CHANNELS["Items"])
    out = _decode(
        _call(
            srv.sellercloud_list_channels, company_id=SANDBOX_COMPANY_PRIMARY
        )
    )
    assert out["ok"] is True
    assert out["data"]["count"] == 2


# ---- get_channel_listing ----------------------------------------------


def test_get_channel_listing_happy(monkeypatch):
    _install_fake_client(
        monkeypatch, get_channel_listing=SAMPLE_CHANNEL_LISTING["Items"][0]
    )
    out = _decode(
        _call(
            srv.sellercloud_get_channel_listing,
            channel_id=7001,
            sku="ACME-WIDGET-001",
        )
    )
    assert out["ok"] is True
    assert out["data"]["ChannelID"] == 7001


def test_get_channel_listing_rejects_bad_args(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(
        _call(srv.sellercloud_get_channel_listing, channel_id=0, sku="x")
    )
    assert out["ok"] is False
    out = _decode(
        _call(srv.sellercloud_get_channel_listing, channel_id=7001, sku="")
    )
    assert out["ok"] is False


# ---- env-driven init --------------------------------------------------


def test_resolve_company_id_raises_without_default(monkeypatch):
    from sellercloud_mcp.config import Settings

    monkeypatch.setattr(
        srv,
        "_settings",
        Settings(
            api_url="https://sandbox.api.sellercloud.example/rest/",
            username="u",
            password="p",
            default_company_id=None,
            http_timeout=10,
            max_retries=2,
        ),
    )
    with pytest.raises(ValueError, match="company_id is required"):
        srv._resolve_company_id(None)
