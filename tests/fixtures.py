"""Synthetic fixtures used across the test suite.

All identifiers, names, and SKUs are invented for testing. Any resemblance
to a real ecommerce business is coincidental — this file must never gain
real-world identifiers.
"""

from __future__ import annotations

# Sandbox CompanyIDs for the test fixtures only. Pick deliberately
# unrealistic numbers so it's obvious if they ever leak into a real API
# call by accident.
SANDBOX_COMPANY_PRIMARY = 9001
SANDBOX_COMPANY_SECONDARY = 9002

SAMPLE_TOKEN_RESPONSE = {
    "access_token": "test-bearer-token-please-do-not-use-in-production",
    "expires_in": 3600,
    "token_type": "Bearer",
}

SAMPLE_PRODUCT = {
    "ID": "ACME-WIDGET-001",
    "ProductName": "Acme Lorem Widget, Standard",
    "CompanyID": SANDBOX_COMPANY_PRIMARY,
    "Price": 29.99,
    "Description": "A perfectly cromulent widget for testing purposes.",
}

SAMPLE_PRODUCT_LIST = {
    "Items": [
        SAMPLE_PRODUCT,
        {
            "ID": "ACME-WIDGET-002",
            "ProductName": "Acme Lorem Widget, Deluxe",
            "CompanyID": SANDBOX_COMPANY_PRIMARY,
            "Price": 49.99,
        },
    ],
    "TotalResults": 2,
}

SAMPLE_INVENTORY = {
    "ID": "ACME-WIDGET-001",
    "ProductName": "Acme Lorem Widget, Standard",
    "CompanyID": SANDBOX_COMPANY_PRIMARY,
    "InventoryAvailableQty": 42,
    "PhysicalQty": 50,
    "ReservedQty": 8,
    "OnOrder": 100,
    "WarehouseName": "Lorem Ipsum DC",
    "IsSellAble": True,
}

SAMPLE_ORDER_LIST_PAGE_1 = {
    "Items": [
        {
            "OrderID": 100001,
            "OrderSource": 6,
            "CompanyID": SANDBOX_COMPANY_PRIMARY,
            "GrandTotal": 59.98,
            "OrderSourceOrderID": "TEST-ORD-100001",
        },
        {
            "OrderID": 100002,
            "OrderSource": 1,
            "CompanyID": SANDBOX_COMPANY_PRIMARY,
            "GrandTotal": 12.50,
            "OrderSourceOrderID": "TEST-ORD-100002",
        },
    ],
    "TotalResults": 3,
}

SAMPLE_ORDER_LIST_PAGE_2 = {
    "Items": [
        {
            "OrderID": 100003,
            "OrderSource": 4,
            "CompanyID": SANDBOX_COMPANY_PRIMARY,
            "GrandTotal": 199.00,
            "OrderSourceOrderID": "TEST-ORD-100003",
        }
    ],
    "TotalResults": 3,
}

SAMPLE_ORDER_DETAIL = {
    "OrderID": 100001,
    "CompanyID": SANDBOX_COMPANY_PRIMARY,
    "OrderSource": 6,
    "GrandTotal": 59.98,
    "OrderSourceOrderID": "TEST-ORD-100001",
    "ShippingCountry": "ZZ",
    "DestinationCountry": "ZZ",
    "Items": [
        {"ProductID": "ACME-WIDGET-001", "Qty": 1, "Price": 29.99},
        {"ProductID": "ACME-WIDGET-002", "Qty": 1, "Price": 29.99},
    ],
}

SAMPLE_CHANNELS = {
    "Items": [
        {
            "ChannelID": 7001,
            "Name": "Sandbox Marketplace",
            "CompanyID": SANDBOX_COMPANY_PRIMARY,
            "Active": True,
        },
        {
            "ChannelID": 7002,
            "Name": "Sandbox Storefront",
            "CompanyID": SANDBOX_COMPANY_PRIMARY,
            "Active": True,
        },
    ],
    "TotalResults": 2,
}

SAMPLE_CHANNEL_LISTING = {
    "Items": [
        {
            "ChannelID": 7001,
            "ProductID": "ACME-WIDGET-001",
            "Title": "Acme Lorem Widget, Standard",
            "Price": 29.99,
            "Active": True,
        }
    ],
    "TotalResults": 1,
}
