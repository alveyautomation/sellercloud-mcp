"""Tests for the SellerCloud HTTP client.

All tests use a mocked `requests.Session` — no live HTTP, no real
credentials. Synthetic fixtures defined in tests/fixtures.py.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from sellercloud_mcp.client import SellerCloudClient, SellerCloudError, _format_datetime
from tests.fixtures import (
    SAMPLE_CHANNEL_LISTING,
    SAMPLE_CHANNELS,
    SAMPLE_INVENTORY,
    SAMPLE_ORDER_DETAIL,
    SAMPLE_ORDER_LIST_PAGE_1,
    SAMPLE_ORDER_LIST_PAGE_2,
    SAMPLE_PRODUCT,
    SAMPLE_PRODUCT_LIST,
    SAMPLE_TOKEN_RESPONSE,
    SANDBOX_COMPANY_PRIMARY,
)


def _ok_response(json_body: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 400
    resp.json.return_value = json_body
    return resp


def _err_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = False
    resp.json.return_value = {}
    return resp


def _token_post_responder(url, json=None, headers=None, timeout=None):
    if url.endswith("/api/token"):
        return _ok_response(SAMPLE_TOKEN_RESPONSE)
    raise AssertionError(f"Unexpected POST: {url}")


def _make_client(session: MagicMock) -> SellerCloudClient:
    return SellerCloudClient(
        base_url="https://sandbox.api.sellercloud.example/rest/",
        username="u",
        password="p",
        timeout=5,
        max_retries=3,
        session=session,
    )


# ---- token / auth ------------------------------------------------------


def test_token_acquired_on_first_request():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"Items": [], "TotalResults": 0})

    client = _make_client(session)
    client.search_products(query="anything", company_id=SANDBOX_COMPANY_PRIMARY)

    # Token POST happened exactly once
    assert session.post.call_count == 1
    # Subsequent call reuses the cached token
    client.search_products(query="anything", company_id=SANDBOX_COMPANY_PRIMARY)
    assert session.post.call_count == 1


def test_token_failure_raises_sellercloud_error():
    session = MagicMock()
    session.post.return_value = _err_response(401)
    client = _make_client(session)
    with pytest.raises(SellerCloudError, match="Failed to obtain SellerCloud token"):
        client.search_products(query="x", company_id=SANDBOX_COMPANY_PRIMARY)


def test_token_response_missing_access_token():
    session = MagicMock()
    session.post.return_value = _ok_response({"expires_in": 3600})
    client = _make_client(session)
    with pytest.raises(SellerCloudError, match="missing 'access_token'"):
        client.search_products(query="x", company_id=SANDBOX_COMPANY_PRIMARY)


def test_401_during_request_refreshes_token_and_retries():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _err_response(401),
        _ok_response(SAMPLE_PRODUCT_LIST),
    ]
    client = _make_client(session)
    result = client.search_products(query="widget", company_id=SANDBOX_COMPANY_PRIMARY)
    assert result["TotalResults"] == 2
    # First token + refresh = 2 POSTs
    assert session.post.call_count == 2
    assert session.request.call_count == 2


# ---- error / retry handling -------------------------------------------


def test_500_response_retries_then_raises():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(500)
    client = _make_client(session)
    with pytest.raises(SellerCloudError, match="Transient SellerCloud error"):
        client.search_products(query="x", company_id=SANDBOX_COMPANY_PRIMARY)
    assert session.request.call_count == 3  # max_retries


def test_connection_error_retries(monkeypatch):
    # Patch sleep to keep tests fast
    import sellercloud_mcp.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)

    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        requests.ConnectionError("boom"),
        _ok_response(SAMPLE_PRODUCT_LIST),
    ]
    client = _make_client(session)
    result = client.search_products(query="x", company_id=SANDBOX_COMPANY_PRIMARY)
    assert result["TotalResults"] == 2


def test_404_does_not_retry():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    with pytest.raises(SellerCloudError) as exc_info:
        client.search_products(query="x", company_id=SANDBOX_COMPANY_PRIMARY)
    assert exc_info.value.status_code == 404
    assert session.request.call_count == 1


# ---- read endpoints ----------------------------------------------------


def test_search_products_passes_expected_params():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_PRODUCT_LIST)
    client = _make_client(session)

    client.search_products(query="widget", company_id=SANDBOX_COMPANY_PRIMARY)

    args, kwargs = session.request.call_args
    assert args[0] == "GET"
    assert args[1].endswith("/api/Catalog")
    params = kwargs["params"]
    assert params["model.search"] == "widget"
    assert params["model.companyID"] == SANDBOX_COMPANY_PRIMARY
    assert params["model.pageNumber"] == 1


def test_get_product_returns_exact_match():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"Items": [SAMPLE_PRODUCT], "TotalResults": 1}
    )
    client = _make_client(session)
    result = client.get_product(sku="ACME-WIDGET-001", company_id=SANDBOX_COMPANY_PRIMARY)
    assert result is not None
    assert result["ID"] == "ACME-WIDGET-001"


def test_get_product_returns_none_on_no_match():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"Items": [], "TotalResults": 0})
    client = _make_client(session)
    result = client.get_product(sku="DOES-NOT-EXIST", company_id=SANDBOX_COMPANY_PRIMARY)
    assert result is None


def test_search_orders_handles_pagination():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.side_effect = [
        _ok_response(SAMPLE_ORDER_LIST_PAGE_1),
        _ok_response(SAMPLE_ORDER_LIST_PAGE_2),
    ]
    client = _make_client(session)

    out = list(
        client.search_orders(
            date_from=date(2026, 4, 26),
            date_to=date(2026, 4, 26),
            company_id=SANDBOX_COMPANY_PRIMARY,
        )
    )
    assert len(out) == 3
    assert {o["OrderID"] for o in out} == {100001, 100002, 100003}


def test_search_orders_rejects_inverted_range():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    client = _make_client(session)
    with pytest.raises(ValueError, match="date_from must be <= date_to"):
        list(
            client.search_orders(
                date_from=date(2026, 4, 26),
                date_to=date(2026, 4, 25),
            )
        )


def test_get_order_returns_detail():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_ORDER_DETAIL)
    client = _make_client(session)
    result = client.get_order(100001)
    assert result is not None
    assert result["OrderID"] == 100001
    assert len(result["Items"]) == 2


def test_get_order_returns_none_on_404():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _err_response(404)
    client = _make_client(session)
    assert client.get_order(99999999) is None


def test_get_inventory_returns_record():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(
        {"Items": [SAMPLE_INVENTORY], "TotalResults": 1}
    )
    client = _make_client(session)
    inv = client.get_inventory(sku="ACME-WIDGET-001", company_id=SANDBOX_COMPANY_PRIMARY)
    assert inv is not None
    assert inv["InventoryAvailableQty"] == 42


def test_list_channels_returns_items():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_CHANNELS)
    client = _make_client(session)
    out = client.list_channels(company_id=SANDBOX_COMPANY_PRIMARY)
    assert len(out) == 2
    assert {c["ChannelID"] for c in out} == {7001, 7002}


def test_get_channel_listing_returns_match():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response(SAMPLE_CHANNEL_LISTING)
    client = _make_client(session)
    listing = client.get_channel_listing(channel_id=7001, sku="ACME-WIDGET-001")
    assert listing is not None
    assert listing["ChannelID"] == 7001


def test_format_datetime_for_date():
    assert _format_datetime(date(2026, 1, 5), end=False) == "01/05/2026 00:00"
    assert _format_datetime(date(2026, 12, 31), end=True) == "12/31/2026 23:59"


def test_base_url_normalization():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"Items": [], "TotalResults": 0})
    client = SellerCloudClient(
        base_url="https://sandbox.api.sellercloud.example/rest",  # no trailing slash
        username="u",
        password="p",
        session=session,
    )
    client.search_products(query="x", company_id=SANDBOX_COMPANY_PRIMARY)
    assert client.base_url.endswith("/")


def test_max_retries_clamped_to_minimum_one():
    session = MagicMock()
    session.post.side_effect = _token_post_responder
    session.request.return_value = _ok_response({"Items": [], "TotalResults": 0})
    client = SellerCloudClient(
        base_url="https://sandbox.api.sellercloud.example/rest/",
        username="u",
        password="p",
        max_retries=0,  # nonsense value
        session=session,
    )
    # Should still execute once
    client.search_products(query="x", company_id=SANDBOX_COMPANY_PRIMARY)
