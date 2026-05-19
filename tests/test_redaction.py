"""Tests for the redaction helper used in logs."""

from __future__ import annotations

from gbm_mx_api.transport.redaction import REDACTED, redact


def test_redacts_known_sensitive_keys() -> None:
    obj = {
        "accessToken": "abc.def.ghi",
        "user": "carlos@example.com",
        "password": "supersecret",
        "harmless": "ok",
    }
    out = redact(obj)
    assert out["accessToken"] == REDACTED
    assert out["user"] == REDACTED
    assert out["password"] == REDACTED
    assert out["harmless"] == "ok"


def test_preserves_falsy_sensitive_values() -> None:
    # Empty / None / 0 are not secrets; keep them visible to aid debugging.
    obj = {"accessToken": "", "session": None, "user": "real@example.com"}
    out = redact(obj)
    assert out["accessToken"] == ""
    assert out["session"] is None
    assert out["user"] == REDACTED


def test_traverses_nested_structures() -> None:
    obj = {
        "outer": {
            "inner": [
                {"refreshToken": "tok-1"},
                {"safe": "value"},
            ]
        }
    }
    out = redact(obj)
    assert out["outer"]["inner"][0]["refreshToken"] == REDACTED
    assert out["outer"]["inner"][1]["safe"] == "value"


def test_truncates_long_strings_even_under_unknown_key() -> None:
    long_jwt = "x" * 1500
    obj = {"some_unknown_field": long_jwt}
    out = redact(obj, max_str=200)
    assert isinstance(out["some_unknown_field"], str)
    assert len(out["some_unknown_field"]) < len(long_jwt)
    assert "1500 chars" in out["some_unknown_field"]


def test_returns_input_for_primitives() -> None:
    assert redact(42) == 42
    assert redact("plain") == "plain"
    assert redact(None) is None
    assert redact(True) is True


def test_email_aware_of_cognito_keys() -> None:
    obj = {"sub": "uuid-1", "cognito:username": "u-2", "custom:legacy_id": "L-3"}
    out = redact(obj)
    assert all(v == REDACTED for v in out.values())
