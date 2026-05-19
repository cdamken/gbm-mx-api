"""Authentication subsystem.

Public surface:

    from gbm_mx_api.auth import login, Session

The :func:`login` function orchestrates the two-step flow (password + TOTP)
and returns a :class:`Session` that can be persisted with
:func:`Session.save` and reloaded with :func:`Session.load`.
"""

from __future__ import annotations

from gbm_mx_api.auth.login import (
    DEFAULT_CLIENT_ID,
    complete_mfa,
    detect_geo,
    login,
    start_login,
)
from gbm_mx_api.auth.session import Session

__all__ = [
    "DEFAULT_CLIENT_ID",
    "Session",
    "complete_mfa",
    "detect_geo",
    "login",
    "start_login",
]
