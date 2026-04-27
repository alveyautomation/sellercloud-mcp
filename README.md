# sellercloud-mcp

> The first Model Context Protocol server for SellerCloud. Plug Claude into your catalog, inventory, orders, and channel listings â€” read-only, in five minutes.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.x-purple.svg)](https://modelcontextprotocol.io)

## Why this exists

SellerCloud has no public SDK. Their REST API is well-documented but unbranded â€” every team that automates against it ends up writing the same auth-and-pagination glue from scratch.

If you use Claude (or any MCP-aware AI assistant) to operate ecommerce day-to-day, that gap is the difference between *"summarize today's orders"* working out of the box and *"summarize today's orders"* requiring a custom integration.

`sellercloud-mcp` closes that gap. It's a tiny, well-tested, MIT-licensed MCP server that exposes seven read-only SellerCloud endpoints to any MCP client. Built from years of running ecommerce automation at scale.

## What you can do with it

Wire this server into Claude Code, Claude Desktop, or any MCP host, then ask things like:

- *"Search for any SKU containing `WIDGET` and show me the inventory levels."*
- *"How many orders did we ship yesterday across all marketplaces? Group by channel."*
- *"Pull order 100001 and tell me which line items shipped."*
- *"List the channels configured for company 9001 and show which ones are active."*
- *"For SKU `ACME-001`, compare the price across every channel listing."*

Claude reads your catalog directly. No copy-paste, no spreadsheets, no custom pipelines.

## Tools (v0.1, all read-only)

| Tool                              | What it does                                                |
| --------------------------------- | ----------------------------------------------------------- |
| `sellercloud_search_products`     | Free-text search across catalog (name, SKU, attributes).    |
| `sellercloud_get_product`         | Fetch one product by exact SKU.                             |
| `sellercloud_search_orders`       | List orders in a date window, optionally scoped by company. |
| `sellercloud_get_order`           | Fetch one order by ID, including line items.                |
| `sellercloud_get_inventory`       | Current on-hand / reserved / on-order qty for one SKU.      |
| `sellercloud_list_channels`       | List configured marketplace/channel feeds.                  |
| `sellercloud_get_channel_listing` | Per-channel listing detail for one SKU.                     |

Write endpoints (create order, update inventory, push channel changes) are intentionally **not** in v0.1. They are planned for v0.2 once read-only ergonomics settle.

## Install

```bash
pip install sellercloud-mcp
```

> v0.1 ships from this repository. PyPI publication is pending â€” for now, install with `pip install git+https://github.com/alveyautomation/sellercloud-mcp` or clone and run `pip install -e .` locally.

## Configure credentials

The server reads everything from environment variables. Copy `.env.example` to `.env` and fill in your tenant:

```bash
SELLERCLOUD_API_URL=https://your-team.api.sellercloud.com/rest/
SELLERCLOUD_USERNAME=your-username
SELLERCLOUD_PASSWORD=your-password
SELLERCLOUD_DEFAULT_COMPANY_ID=        # optional fallback
SELLERCLOUD_HTTP_TIMEOUT=60            # optional, seconds
SELLERCLOUD_MAX_RETRIES=3              # optional
```

> **Use a read-only SellerCloud account.** v0.1 only calls `GET` endpoints, but defense in depth means you should hand the server a dedicated user that *cannot* modify anything. When v0.2 lands with write tools, opt-in by upgrading the credential â€” never the other way around.

## Wire into Claude Code

Add to `~/.claude/claude_code_config.json` (or your project's MCP config):

```json
{
  "mcpServers": {
    "sellercloud": {
      "command": "sellercloud-mcp",
      "env": {
        "SELLERCLOUD_API_URL": "https://your-team.api.sellercloud.com/rest/",
        "SELLERCLOUD_USERNAME": "your-username",
        "SELLERCLOUD_PASSWORD": "your-password",
        "SELLERCLOUD_DEFAULT_COMPANY_ID": "9001"
      }
    }
  }
}
```

Restart Claude Code. The seven `sellercloud_*` tools will appear in any new session.

## Wire into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and add the same `mcpServers` block as above. Restart the desktop app.

## Tool reference

Every tool returns a JSON envelope:

```json
{ "ok": true,  "data": { ... } }
{ "ok": false, "error": "human-readable message" }
```

### `sellercloud_search_products`

```python
sellercloud_search_products(
    query: str,                          # required
    company_id: int | None = None,       # falls back to default if unset
    page: int = 1,
    page_size: int = 50,                 # capped at 50 by SellerCloud
)
```

Example response:

```json
{
  "ok": true,
  "data": {
    "items": [
      { "ID": "ACME-WIDGET-001", "ProductName": "Acme Widget, Standard", "Price": 29.99 }
    ],
    "total": 1,
    "page": 1,
    "page_size": 50
  }
}
```

### `sellercloud_get_product`

```python
sellercloud_get_product(sku: str, company_id: int | None = None)
```

Returns the catalog record, or `data: null` if the SKU is not in the company's catalog.

### `sellercloud_search_orders`

```python
sellercloud_search_orders(
    date_from: str,                      # ISO date "YYYY-MM-DD"
    date_to: str,                        # ISO date "YYYY-MM-DD"
    company_id: int | None = None,
    query: str | None = None,
    limit: int = 200,                    # max 1000
)
```

Pagination is handled transparently â€” SellerCloud caps page size at 50, but the tool collects pages up to `limit`. The response includes `limit_reached: true` when there were more orders than `limit` allowed.

### `sellercloud_get_order`

```python
sellercloud_get_order(order_id: int)
```

Returns the full order record (with `Items[]`), or `data: null` for a 404.

### `sellercloud_get_inventory`

```python
sellercloud_get_inventory(sku: str, company_id: int | None = None)
```

The returned record includes:

- `InventoryAvailableQty` â€” what the API considers sellable right now
- `PhysicalQty` â€” on-hand
- `ReservedQty` â€” held for open orders
- `OnOrder` â€” incoming PO qty

Use `InventoryAvailableQty` as the canonical "qty I can sell" number.

### `sellercloud_list_channels`

```python
sellercloud_list_channels(company_id: int | None = None)
```

Returns the list of configured channel feeds for the company. Each record includes `ChannelID`, `Name`, and `Active`.

### `sellercloud_get_channel_listing`

```python
sellercloud_get_channel_listing(channel_id: int, sku: str)
```

Per-channel listing detail. Useful for spot-checking prices across marketplaces.

## Local development

```bash
git clone https://github.com/alveyautomation/sellercloud-mcp
cd sellercloud-mcp
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                                # 44 tests, ~4s
```

Pre-commit hooks (gitleaks, ruff, formatter, tenant-fingerprint scrubber):

```bash
pip install pre-commit
pre-commit install
```

Integration tests against a real SellerCloud sandbox account are gated behind `SELLERCLOUD_INTEGRATION_TESTS=1`. They are not required for normal contribution.

## Troubleshooting

**`Failed to obtain SellerCloud token`** â€” username/password rejected. Most common cause: the account has 2FA enabled or is locked out. SellerCloud's `POST /api/token` endpoint expects a non-2FA service account.

**`Missing required environment variables`** â€” the server tried to start before its `.env` was loaded. Either export the vars in the parent shell, or ensure your MCP host config includes them in the `env` block.

**Empty results despite known data** â€” confirm the `company_id` is correct. SellerCloud returns only the authenticated user's *default* company unless you pass `companyID` explicitly.

**Pagination feels slow** â€” page size is capped at 50 by SellerCloud, not by us. For large date windows, expect multiple round-trips.

## Contributing

Issues and pull requests welcome. Please:

- Run `pytest` before opening a PR (`pip install -e ".[dev]"`).
- Run `pre-commit run --all-files`.
- Keep additions to v0.1 scope read-only. Write endpoints land in v0.2.
- Synthetic data only in tests â€” no real SKUs, customer names, or order numbers.

## License

MIT â€” see [LICENSE](LICENSE).

## Disclaimer

`sellercloud-mcp` is an unofficial, third-party integration. It is **not endorsed by, affiliated with, or supported by SellerCloud, Inc.** "SellerCloud" is a trademark of SellerCloud, Inc. Use at your own risk; verify behavior against your tenant before depending on it for production decisions.

