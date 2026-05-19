"""JSON fixtures shaped after real GBM responses captured in Phase 0.

All values are sanitized — UUIDs and IDs are stable but fake.
"""

from __future__ import annotations

CONTRACTS_RESPONSE: list[dict] = [
    {
        "contract_id": "00000000-0000-4000-8000-000000000001",
        "first_name": "Test",
        "middle_name": "User",
        "last_name": "Example",
        "legacy_contract_id": "AB12CD",
        "contract_status": "active",
        "opening_type": "long_opening",
        "is_legacy": False,
        "is_migrated": False,
        "is_dashboard_blocked": False,
        "created_at": "2026-01-07T15:59:31.077165+00:00",
    }
]


ACCOUNTS_RESPONSE: list[dict] = [
    {
        "account_id": "00000000-0000-4000-8000-000000000010",
        "legacy_contract_id": "AB12CD05",
        "name": "Mi Trading",
        "number": 5,
        "management_type_template": "trading",
        "position": {"amount": 151536.95, "currency": "MXN"},
        "plus_minus": {"amount": 3292.88, "currency": "MXN"},
        "plus_minus_percentage": 0.0285,
        "status": "active",
        "collecting_account": "600000000000000000",
        "profile_type": "not_applicable",
        "created_at": "2026-04-01T17:24:42.178542+00:00",
    },
    {
        "account_id": "00000000-0000-4000-8000-000000000020",
        "legacy_contract_id": "AB12CD03",
        "name": "USA",
        "number": 3,
        "management_type_template": "trading_usa",
        "position": {"amount": 393656.24, "currency": "MXN"},
        "plus_minus": {"amount": 0.0, "currency": "MXN"},
        "plus_minus_percentage": 0.0,
        "status": "active",
        "collecting_account": "600000000000000001",
        "profile_type": "not_applicable",
        "created_at": "2026-01-23T07:21:33.1165+00:00",
    },
]


POSITION_SUMMARY_RESPONSE: dict = {
    "mercadosGlobalesSIC": [
        {
            "positionValueType": 0,
            "issueId": "AMD *",
            "issueName": "ADVANCED MICRO DEVICES INC.",
            "instrumentType": 2,
            "quantity": 2.0,
            "averagePrice": 7518.75,
            "lastPrice": 7272.55,
            "closePrice": 7357.16,
            "weightedAveragePrice": 0.0,
            "yieldValue": -492.4,
            "marketValue": 14545.1,
            "dailyVariationPercentage": -0.0115,
            "historicalVariationPercentage": -0.0327,
            "averageCost": 15037.5,
            "positionPercentage": 0.0961,
        },
        {
            "positionValueType": 0,
            "issueId": "Subtotal",
            "instrumentType": 0,
            "quantity": 0.0,
            "averagePrice": 0.0,
            "lastPrice": 125712.12,
            "closePrice": 133322.62,
            "weightedAveragePrice": 0.0,
            "yieldValue": -3938.8,
            "marketValue": 125712.12,
            "dailyVariationPercentage": -0.057,
            "historicalVariationPercentage": -0.0304,
            "averageCost": 129650.92,
            "positionPercentage": 0.8303,
        },
    ],
    "mercadoCapitales": [
        {
            "positionValueType": 1,
            "issueId": "NAFTRAC ISHRS",
            "issueName": "NACIONAL FINANCIERA S.N.C",
            "instrumentType": 0,
            "quantity": 5.0,
            "averagePrice": 69.77,
            "lastPrice": 68.06,
            "closePrice": 67.88,
            "weightedAveragePrice": 0.0,
            "yieldValue": -8.55,
            "marketValue": 340.3,
            "dailyVariationPercentage": 0.0027,
            "historicalVariationPercentage": -0.0245,
            "averageCost": 348.85,
            "positionPercentage": 0.0022,
        }
    ],
    "sociedadesInversionDeuda": [],
    "efectivo": [],
    "totalPortfolioValue": [
        {
            "positionValueType": 1000,
            "issueId": "Valor total de la cartera",
            "issueName": "Valor total de la cartera",
            "instrumentType": -1,
            "quantity": 0.0,
            "averagePrice": 0.0,
            "lastPrice": 0.0,
            "closePrice": 0.0,
            "weightedAveragePrice": 0.0,
            "yieldValue": 151405.11,
            "marketValue": 151405.11,
            "dailyVariationPercentage": 0.0,
            "historicalVariationPercentage": 0.0,
            "averageCost": 0.0,
            "positionPercentage": 1.0,
        }
    ],
}


def blotter_response(orders: list[dict]) -> dict:
    """Build a blotter envelope wrapping the given ordersList."""
    return {"getRealTimePosition": {}, "ordersList": orders}


# A representative day with one FILLED order (status=7) and one CANCELLED (5).
BLOTTER_TWO_ORDERS: dict = blotter_response(
    [
        {
            "accountId": "AB12CD05",
            "algoTradingTypeId": 0,
            "assignedQuantity": 1,
            "averagePrice": 8692.24,
            "bitBuy": True,
            "cancelMessage": "",
            "cancelQuantity": 0,
            "capitalOrderTypeId": 1,
            "commision": 21.73,
            "duration": 0,
            "gbmIntProcessStatus": 7,
            "instrumentType": 2,
            "isCancelable": False,
            "issueId": "WDC *",
            "iva": 3.48,
            "mainOrderAMId": 0,
            "maxFloor": 0,
            "minQty": 0,
            "originalQuantity": 1,
            "pegOffsetValue": 0,
            "predespachador": False,
            "preorderId": 0,
            "price": 8692.24,
            "processDate": "2026-05-14T08:30:49.64-06:00",
            "sobId": 109142599,
            "stopPrice": 0,
            "treasuryOrderTypeId": 0,
            "triggerPrice": 0,
            "vigencia": "DIA",
            "vigenciaId": 0,
        },
        {
            "accountId": "AB12CD05",
            "algoTradingTypeId": 0,
            "assignedQuantity": 0,
            "averagePrice": 0.0,
            "bitBuy": True,
            "cancelMessage": "User cancelled",
            "cancelQuantity": 2,
            "capitalOrderTypeId": 1,
            "commision": 0.0,
            "duration": 0,
            "gbmIntProcessStatus": 5,
            "instrumentType": 0,
            "isCancelable": False,
            "issueId": "GAP B",
            "iva": 0.0,
            "mainOrderAMId": 0,
            "maxFloor": 0,
            "minQty": 0,
            "originalQuantity": 2,
            "pegOffsetValue": 0,
            "predespachador": False,
            "preorderId": 0,
            "price": 400.0,
            "processDate": "2026-05-14T07:08:00.00-06:00",
            "sobId": 109116247,
            "stopPrice": 0,
            "treasuryOrderTypeId": 0,
            "triggerPrice": 0,
            "vigencia": "DIA",
            "vigenciaId": 0,
        },
    ]
)
