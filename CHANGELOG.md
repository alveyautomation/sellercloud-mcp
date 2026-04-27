# Changelog

All notable changes to `sellercloud-mcp` are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-04-26

Initial public release.

### Added

- MCP server entry point (`sellercloud_mcp/server.py`) using the official `mcp` Python SDK with `FastMCP`.
- Seven read-only tools:
  - `sellercloud_search_products`
  - `sellercloud_get_product`
  - `sellercloud_search_orders`
  - `sellercloud_get_order`
  - `sellercloud_get_inventory`
  - `sellercloud_list_channels`
  - `sellercloud_get_channel_listing`
- HTTP client (`sellercloud_mcp/client.py`):
  - Username + password → bearer token via `POST /api/token`, cached with ~55 min TTL.
  - Automatic token refresh on `401`.
  - Exponential backoff retry on transient `5xx` and connection errors.
  - Transparent pagination for `search_orders`.
- Configuration via environment variables (`sellercloud_mcp/config.py`).
- Pytest suite with mocked HTTP responses (44 tests, all synthetic fixtures).
- Pre-commit configuration: gitleaks, trufflehog, ruff, ruff-format, tenant-fingerprint scrubber.
- MIT license, security policy, contributing guidance in README.

### Notes

- v0.1 is read-only by design. Write endpoints (create order, update inventory, push channel listings) are planned for v0.2.
- Integration tests against a live SellerCloud sandbox are gated by `SELLERCLOUD_INTEGRATION_TESTS=1` and are not exercised by default.
