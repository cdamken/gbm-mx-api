"""HTTP transport layer.

The :class:`HttpClient` wraps ``httpx`` with:
- Required GBM geo headers (``device-latitude`` / ``device-longitude``).
- Optional Bearer token injection.
- Retry on 5xx (idempotent verbs only).
- Honor ``Retry-After`` on 429.
- Redacting logger that never prints tokens or known sensitive fields.
"""

from __future__ import annotations

from gbm_mx_api.transport.http import HttpClient

__all__ = ["HttpClient"]
