"""HTTP client for the SellerCloud REST API.

The client wraps the public REST surface SellerCloud exposes at the tenant
domain configured in `SELLERCLOUD_API_URL`. Auth is bearer-token based, the client exchanges username/password for a token via `POST /api/token` and
caches it in memory for the lifetime of the instance, refreshing on `401` or
near-expiry.

The client is deliberately small and dependency-light: only `requests` is
required at runtime. State is per-instance, there is no module-level
mutable state, so multiple clients can run in the same process against
different tenants without interfering.

This module is a clean rewrite for public release. It does not import or
inherit any tenant-specific configuration; everything that depends on a
particular SellerCloud account is supplied by the caller.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator, Optional

import requests

logger = logging.getLogger(__name__)

# SellerCloud caps the order list `pageSize` at 50 regardless of the
# requested value. Inventory accepts larger pages.
ORDER_PAGE_SIZE = 50
INVENTORY_PAGE_SIZE = 200

# Refresh the bearer token a few minutes before SellerCloud expires it,
# to avoid a tight race on long-running calls.
_TOKEN_TTL_SECONDS = 3300

# Status codes that warrant a retry. 401 is handled separately (token
# refresh + single retry).
_RETRY_STATUS_CODES = frozenset({500, 502, 503, 504})


class SellerCloudError(Exception):
    """Wraps a non-recoverable SellerCloud response so the MCP layer can
    surface a clean message instead of leaking the raw HTTP exception."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class SellerCloudClient:
    """Thin REST wrapper. Construct once per (tenant, credential) pair."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int = 60,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
    ):
        if not base_url.endswith("/"):
            base_url = base_url + "/"
        self.base_url = base_url
        self._username = username
        self._password = password
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._session = session or requests.Session()

        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    # ---- auth -----------------------------------------------------------

    def _get_token(self) -> str:
        now = datetime.now(timezone.utc)
        if (
            self._token
            and self._token_expires_at
            and now < self._token_expires_at
        ):
            return self._token

        url = f"{self.base_url}api/token"
        resp = self._session.post(
            url,
            json={"Username": self._username, "Password": self._password},
            headers={"Content-Type": "application/json"},
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise SellerCloudError(
                f"Failed to obtain SellerCloud token: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise SellerCloudError(
                "SellerCloud token response missing 'access_token'"
            )
        self._token = token
        self._token_expires_at = now + timedelta(seconds=_TOKEN_TTL_SECONDS)
        return token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept": "application/json",
        }

    # ---- request loop --------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        *,
        json_body: Optional[dict] = None,
    ) -> Any:
        url = f"{self.base_url}{path.lstrip('/')}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    json=json_body,
                    timeout=self._timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            # Token expired mid-request: refresh once and retry inline.
            if resp.status_code == 401:
                self._token = None
                self._token_expires_at = None
                try:
                    resp = self._session.request(
                        method,
                        url,
                        headers=self._headers(),
                        params=params,
                        json=json_body,
                        timeout=self._timeout,
                    )
                except (requests.ConnectionError, requests.Timeout) as exc:
                    last_exc = exc
                    self._sleep_backoff(attempt)
                    continue

            if resp.status_code in _RETRY_STATUS_CODES:
                last_exc = SellerCloudError(
                    f"Transient SellerCloud error: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )
                self._sleep_backoff(attempt)
                continue

            if not resp.ok:
                raise SellerCloudError(
                    f"SellerCloud {method} {path} failed: "
                    f"HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )

            try:
                return resp.json()
            except ValueError as exc:
                raise SellerCloudError(
                    f"SellerCloud {method} {path} returned non-JSON body"
                ) from exc

        if last_exc is not None:
            raise SellerCloudError(
                f"SellerCloud {method} {path} failed after "
                f"{self._max_retries} attempts: {last_exc}"
            ) from last_exc
        raise SellerCloudError(
            f"SellerCloud {method} {path} failed for unknown reason"
        )

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        # Exponential backoff with a small floor: 0.5s, 1s, 2s, 4s ...
        delay = 0.5 * (2 ** (attempt - 1))
        time.sleep(min(delay, 8.0))

    # ---- public read endpoints -----------------------------------------

    def search_products(
        self,
        query: str,
        company_id: int,
        *,
        page: int = 1,
        page_size: int = ORDER_PAGE_SIZE,
    ) -> dict:
        """Search the catalog for `query` across name / SKU / attributes."""
        params = {
            "model.search": query,
            "model.companyID": company_id,
            "model.pageNumber": page,
            "model.pageSize": page_size,
        }
        return self._request("GET", "api/Catalog", params=params)

    def get_product(self, sku: str, company_id: int) -> Optional[dict]:
        """Return the catalog record for an exact SKU, or None if absent."""
        params = {
            "model.productID": sku,
            "model.companyID": company_id,
            "model.pageNumber": 1,
            "model.pageSize": 5,
        }
        data = self._request("GET", "api/Catalog", params=params)
        items = data.get("Items") or []
        sku_upper = sku.upper()
        for item in items:
            candidate = (item.get("ID") or item.get("ProductID") or "").upper()
            if candidate == sku_upper:
                return item
        return items[0] if len(items) == 1 else None

    def search_orders(
        self,
        date_from: date,
        date_to: date,
        company_id: Optional[int] = None,
        *,
        query: Optional[str] = None,
    ) -> Iterator[dict]:
        """Yield every order created in the inclusive [date_from, date_to] range.

        SellerCloud caps page size at 50 regardless of the requested value, so
        callers should expect transparent pagination.
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        page = 1
        yielded = 0
        while True:
            params: dict[str, Any] = {
                "model.createdOnFrom": _format_datetime(date_from, end=False),
                "model.createdOnTo": _format_datetime(date_to, end=True),
                "model.pageNumber": page,
                "model.pageSize": ORDER_PAGE_SIZE,
            }
            if company_id is not None:
                params["model.companyID"] = company_id
            if query:
                params["model.search"] = query

            data = self._request("GET", "api/Orders", params=params)
            items = data.get("Items") or []
            total = data.get("TotalResults", 0)

            for order in items:
                yield order
            yielded += len(items)

            if not items or yielded >= total:
                return
            page += 1

    def get_order(self, order_id: int) -> Optional[dict]:
        """Return full order detail (including line items), or None if missing."""
        try:
            return self._request("GET", f"api/Orders/{order_id}")
        except SellerCloudError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_inventory(self, sku: str, company_id: int) -> Optional[dict]:
        """Return the current inventory record for `sku` at `company_id`."""
        params = {
            "model.inventoryID": sku,
            "model.companyID": company_id,
            "model.pageNumber": 1,
            "model.pageSize": 10,
        }
        data = self._request("GET", "api/Inventory", params=params)
        items = data.get("Items") or []
        sku_upper = sku.upper()
        for item in items:
            candidate = (item.get("ID") or "").strip().upper()
            if candidate == sku_upper:
                return item
        return items[0] if len(items) == 1 else None

    def list_channels(self, company_id: int) -> list[dict]:
        """List configured channel feeds for the given company."""
        params = {"model.companyID": company_id, "model.pageSize": 200}
        data = self._request("GET", "api/Channels", params=params)
        return list(data.get("Items") or [])

    def get_channel_listing(self, channel_id: int, sku: str) -> Optional[dict]:
        """Return the per-channel listing record for `sku`, or None if absent."""
        params = {
            "model.channelID": channel_id,
            "model.productID": sku,
            "model.pageNumber": 1,
            "model.pageSize": 10,
        }
        data = self._request("GET", "api/ChannelListings", params=params)
        items = data.get("Items") or []
        sku_upper = sku.upper()
        for item in items:
            candidate = (item.get("ProductID") or item.get("SKU") or "").upper()
            if candidate == sku_upper:
                return item
        return items[0] if len(items) == 1 else None


def _format_datetime(d: date, *, end: bool) -> str:
    """Format a date as SellerCloud expects: MM/DD/YYYY HH:MM (24h)."""
    if isinstance(d, datetime):
        return f"{d.month:02d}/{d.day:02d}/{d.year} {d.hour:02d}:{d.minute:02d}"
    suffix = "23:59" if end else "00:00"
    return f"{d.month:02d}/{d.day:02d}/{d.year} {suffix}"
