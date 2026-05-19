"""Tests for the Session model and its persistence."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from gbm_mx_api.auth.session import Session


def _make(**overrides: object) -> Session:
    defaults: dict[str, object] = {
        "access_token": "access-1",
        "identity_token": "id-1",
        "refresh_token": "ref-1",
        "expires_in": 3600,
        "latitude": 19.4326,
        "longitude": -99.1332,
        "client_id": "test-client",
    }
    defaults.update(overrides)
    return Session(**defaults)  # type: ignore[arg-type]


def test_expires_at_and_remaining() -> None:
    s = _make(obtained_at=int(time.time()) - 100, expires_in=3600)
    assert 3400 < s.seconds_remaining <= 3500
    assert s.is_expired is False


def test_is_expired_when_past() -> None:
    s = _make(obtained_at=int(time.time()) - 4000, expires_in=3600)
    assert s.seconds_remaining < 0
    assert s.is_expired is True


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    original = _make()
    written_to = original.save(path)
    assert written_to == path.resolve()

    loaded = Session.load(path)
    assert loaded.access_token == original.access_token
    assert loaded.identity_token == original.identity_token
    assert loaded.refresh_token == original.refresh_token
    assert loaded.latitude == original.latitude


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_save_uses_0600_permissions(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    _make().save(path)
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_try_load_returns_none_on_missing(tmp_path: Path) -> None:
    assert Session.try_load(tmp_path / "missing.json") is None


def test_try_load_returns_none_on_corrupt(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert Session.try_load(path) is None
