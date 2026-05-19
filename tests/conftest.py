"""Shared fixtures for tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def fixed_geo() -> tuple[float, float]:
    """Static lat/lon for deterministic tests (avoid hitting ipapi.co)."""
    return 19.4326, -99.1332
