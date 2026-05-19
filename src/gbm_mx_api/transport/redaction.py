"""Recursively redact sensitive values from dicts/lists for safe logging.

The set of sensitive keys is hard-coded and intentionally over-inclusive. We
prefer false positives (redacting too much) over leaking a token in a log.
"""

from __future__ import annotations

from typing import Any

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        # Tokens
        "accessToken",
        "access_token",
        "refreshToken",
        "refresh_token",
        "idToken",
        "id_token",
        "identityToken",
        "identity_token",
        "token",
        "session",
        "sessionId",
        "session_id",
        "mfaToken",
        "mfa_token",
        "challengeId",
        "challenge_id",
        # Credentials
        "password",
        "code",
        "totpCode",
        "totp_code",
        # Personal identifiers
        "user",
        "email",
        "userId",
        "user_id",
        "rfc",
        "curp",
        "phone",
        "phoneNumber",
        "phone_number",
        # GBM-specific identifiers
        "contractId",
        "contract_id",
        "legacyContractId",
        "legacy_contract_id",
        "accountId",
        "account_id",
        "sub",
        "cognito:username",
        "custom:legacy_id",
        # Name fragments
        "firstName",
        "first_name",
        "middleName",
        "middle_name",
        "lastName",
        "last_name",
        "fullName",
        "full_name",
        "displayName",
        "display_name",
        "holderName",
        "holderEmail",
        # Banking
        "collecting_account",
        "clabe",
        "iban",
    }
)

REDACTED = "<REDACTED>"


def redact(obj: Any, *, max_str: int = 200) -> Any:
    """Return a deep copy of ``obj`` with sensitive values replaced.

    - ``dict`` values whose key is in :data:`SENSITIVE_KEYS` become ``"<REDACTED>"``.
    - Long strings (over ``max_str`` chars) get truncated with a length suffix
      to avoid dumping multi-KB JWTs to logs even if the key isn't recognized.
    - Lists are traversed element-wise.
    - Primitives pass through.

    The function never raises; on any unexpected type it returns the input.
    """
    return _redact(obj, max_str=max_str)


def _redact(obj: Any, *, max_str: int) -> Any:
    if isinstance(obj, dict):
        return {
            k: (REDACTED if _is_sensitive(k, v) else _redact(v, max_str=max_str))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(x, max_str=max_str) for x in obj]
    if isinstance(obj, str) and len(obj) > max_str:
        return f"{obj[:30]}...<{len(obj)} chars>"
    return obj


def _is_sensitive(key: str, value: Any) -> bool:
    if key not in SENSITIVE_KEYS:
        return False
    # Don't bother redacting empty / zero / falsy values — they carry no secret.
    return value not in (None, "", 0, False)
