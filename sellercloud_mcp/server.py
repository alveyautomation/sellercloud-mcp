"""MCP server entry point.

Exposes seven read-only tools that wrap SellerCloud's REST API. The server
uses stdio transport, which is the standard MCP transport for desktop Claude
clients (Claude Code, Claude Desktop, IDE extensions).

Run via `python -m sellercloud_mcp` or the `sellercloud-mcp` CLI command.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .client import SellerCloudClient, SellerCloudError
from .config import Settings

logger = logging.getLogger(__name__)

mcp = FastMCP("sellercloud-mcp")

# Lazy singletons. We don't want to require credentials at import time —
# the MCP host may launch the server with a degenerate environment for
# capability discovery.
_settings: Optional[Settings] = None
_client: Optional[SellerCloudClient] = None


def _get_client() -> SellerCloudClient:
    global _settings, _client
    if _client is None:
        _settings = Settings.from_env()
        _client = SellerCloudClient(
            base_url=_settings.api_url,
            username=_settings.username,
            password=_settings.password,
            timeout=_settings.http_timeout,
            max_retries=_settings.max_retries,
        )
    return _client


def _resolve_company_id(company_id: Optional[int]) -> int:
    if company_id is not None:
        return company_id
    if _settings is None:
        # Trigger lazy init; updates _settings as a side effect.
        _get_client()
    assert _settings is not None
    if _settings.default_company_id is None:
        raise ValueError(
            "company_id is required. Set SELLERCLOUD_DEFAULT_COMPANY_ID "
            "to skip this argument on every call."
        )
    return _settings.default_company_id


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, default=_json_default, indent=2)


def _err(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, indent=2)


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO date (YYYY-MM-DD); got {value!r}"
        ) from exc


# ---- tools -------------------------------------------------------------


@mcp.tool()
def sellercloud_search_products(
    query: str,
    company_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> str:
    """Search the SellerCloud catalog by name, SKU, or attribute.

    Args:
        query: Free-text search string. Matches against product name,
            SKU, and indexed attributes.
        company_id: SellerCloud CompanyID to scope the search to. Falls
            back to SELLERCLOUD_DEFAULT_COMPANY_ID if omitted.
        page: 1-indexed page number.
        page_size: Page size (max 50 enforced server-side).

    Returns:
        JSON envelope: {"ok": true, "data": {"items": [...], "total": N}}.
    """
    if not query or not query.strip():
        return _err("query is required and must be non-empty")
    try:
        cid = _resolve_company_id(company_id)
        result = _get_client().search_products(
            query=query.strip(),
            company_id=cid,
            page=max(1, page),
            page_size=max(1, min(page_size, 50)),
        )
        return _ok(
            {
                "items": result.get("Items") or [],
                "total": result.get("TotalResults", 0),
                "page": page,
                "page_size": page_size,
            }
        )
    except (ValueError, SellerCloudError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def sellercloud_get_product(
    sku: str,
    company_id: Optional[int] = None,
) -> str:
    """Fetch the full catalog record for a single SKU.

    Args:
        sku: Exact SKU / ProductID to look up.
        company_id: CompanyID scoping the lookup.

    Returns:
        JSON envelope. `data` is the product record, or null when the
        SKU is not present in the company's catalog.
    """
    if not sku or not sku.strip():
        return _err("sku is required and must be non-empty")
    try:
        cid = _resolve_company_id(company_id)
        product = _get_client().get_product(sku=sku.strip(), company_id=cid)
        return _ok(product)
    except (ValueError, SellerCloudError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def sellercloud_search_orders(
    date_from: str,
    date_to: str,
    company_id: Optional[int] = None,
    query: Optional[str] = None,
    limit: int = 200,
) -> str:
    """Search orders created in the inclusive [date_from, date_to] window.

    Args:
        date_from: ISO date (YYYY-MM-DD), start of window.
        date_to: ISO date (YYYY-MM-DD), end of window.
        company_id: CompanyID to scope the search to. If omitted, returns
            orders for the authenticated user's default company.
        query: Optional free-text filter applied server-side.
        limit: Cap on yielded orders (default 200, max 1000). The
            underlying API caps page size at 50; pagination is handled
            transparently.

    Returns:
        JSON envelope. `data.orders` is the list of order records.
    """
    try:
        df = _parse_date(date_from, "date_from")
        dt = _parse_date(date_to, "date_to")
        cid = company_id if company_id is not None else _maybe_default_company()
        capped_limit = max(1, min(limit, 1000))
        client = _get_client()
        out: list[dict] = []
        for order in client.search_orders(
            date_from=df,
            date_to=dt,
            company_id=cid,
            query=query.strip() if query else None,
        ):
            out.append(order)
            if len(out) >= capped_limit:
                break
        return _ok(
            {
                "orders": out,
                "count": len(out),
                "date_from": df.isoformat(),
                "date_to": dt.isoformat(),
                "company_id": cid,
                "limit_reached": len(out) >= capped_limit,
            }
        )
    except (ValueError, SellerCloudError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def sellercloud_get_order(order_id: int) -> str:
    """Fetch full order detail including line items.

    Args:
        order_id: SellerCloud OrderID (integer).

    Returns:
        JSON envelope. `data` is the order record, or null if the order
        does not exist.
    """
    if not isinstance(order_id, int) or order_id <= 0:
        return _err("order_id must be a positive integer")
    try:
        order = _get_client().get_order(order_id=order_id)
        return _ok(order)
    except (ValueError, SellerCloudError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def sellercloud_get_inventory(
    sku: str,
    company_id: Optional[int] = None,
) -> str:
    """Fetch the current inventory record for a single SKU.

    Args:
        sku: Exact SKU / InventoryID.
        company_id: CompanyID scoping the lookup.

    Returns:
        JSON envelope. `data` is the inventory record (with on-hand,
        reserved, on-order, available qty fields), or null if absent.
    """
    if not sku or not sku.strip():
        return _err("sku is required and must be non-empty")
    try:
        cid = _resolve_company_id(company_id)
        inv = _get_client().get_inventory(sku=sku.strip(), company_id=cid)
        return _ok(inv)
    except (ValueError, SellerCloudError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def sellercloud_list_channels(
    company_id: Optional[int] = None,
) -> str:
    """List configured channel feeds for the given company.

    Args:
        company_id: CompanyID scoping the lookup.

    Returns:
        JSON envelope. `data.channels` is the list of channel records.
    """
    try:
        cid = _resolve_company_id(company_id)
        channels = _get_client().list_channels(company_id=cid)
        return _ok({"channels": channels, "count": len(channels)})
    except (ValueError, SellerCloudError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def sellercloud_get_channel_listing(
    channel_id: int,
    sku: str,
) -> str:
    """Fetch the per-channel listing record for a single SKU.

    Args:
        channel_id: SellerCloud ChannelID (integer).
        sku: Exact SKU.

    Returns:
        JSON envelope. `data` is the listing record, or null if the SKU
        is not listed on the given channel.
    """
    if not isinstance(channel_id, int) or channel_id <= 0:
        return _err("channel_id must be a positive integer")
    if not sku or not sku.strip():
        return _err("sku is required and must be non-empty")
    try:
        listing = _get_client().get_channel_listing(
            channel_id=channel_id, sku=sku.strip()
        )
        return _ok(listing)
    except (ValueError, SellerCloudError, RuntimeError) as exc:
        return _err(str(exc))


def _maybe_default_company() -> Optional[int]:
    """Return the configured default CompanyID, or None if unset.

    Unlike `_resolve_company_id`, this never raises — used by tools where
    `company_id` is optional and the API itself accepts no CompanyID.
    """
    if _settings is None:
        _get_client()
    assert _settings is not None
    return _settings.default_company_id


def main() -> None:
    """CLI entry point — runs the MCP server over stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
