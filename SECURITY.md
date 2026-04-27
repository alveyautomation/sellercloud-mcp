# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in `sellercloud-mcp`, please report it
responsibly. Do **not** open a public GitHub issue for security concerns.

**Contact:** open a private security advisory on the GitHub repository (path TBD
post-launch), or email the maintainer directly. We aim to respond to reports
within 72 hours.

## Scope

In scope:

- The MCP server entry point (`sellercloud_mcp/server.py`)
- The SellerCloud HTTP client (`sellercloud_mcp/client.py`)
- Configuration and credential handling (`sellercloud_mcp/config.py`)
- Packaged dependencies and their pinned versions

Out of scope:

- The upstream SellerCloud REST API itself (report directly to SellerCloud, Inc.)
- The MCP protocol specification or the official MCP Python SDK
- Bugs that require an attacker to already control the host running the server

## Credential handling

This project never logs SellerCloud credentials, never persists them outside the
process, and reads them only from environment variables. Bearer tokens are kept
in memory and refreshed on `401`. If you find a code path that violates this,
report it as a security issue.

## Disclosure timeline

Our default policy is coordinated disclosure: we will work with the reporter to
ship a fix and credit the discovery on a timeline that gives users time to
upgrade. The default embargo is 30 days from confirmed reproduction.
