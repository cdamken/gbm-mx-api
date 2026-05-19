"""Internal base class for API modules."""

from __future__ import annotations

from gbm_mx_api.transport.http import HttpClient


class ApiBase:
    """Carries a reference to the shared HttpClient.

    Concrete API modules (``Contracts``, ``Accounts``, ...) subclass this so
    they share a single configured HTTP session per :class:`GbmClient`.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http
