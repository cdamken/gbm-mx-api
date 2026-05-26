"""Authenticated session data model and persistence.

A :class:`Session` holds the tokens issued by GBM after a successful login,
plus the bits needed to keep using them (geo coordinates for headers, client
id, timestamps to know if the access token is still valid).

Sessions are stored as JSON under ``~/.gbm-mx/session.json`` (configurable)
with ``0600`` permissions. They are intentionally kept on disk in plain text
rather than the OS keyring — the trade-off is simplicity and cross-platform
portability; the file should be on a user-only directory.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

DEFAULT_SESSION_PATH = Path.home() / ".gbm-mx" / "session.json"


class Session(BaseModel):
    """Persisted authentication state."""

    access_token: str = Field(..., description="Cognito access token (Bearer).")
    identity_token: str | None = Field(
        default=None, description="Cognito ID token (JWT with user claims)."
    )
    refresh_token: str | None = Field(
        default=None, description="Refresh token (use not yet implemented)."
    )
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(
        default=3600, description="Seconds the access token lasts from obtained_at."
    )
    obtained_at: int = Field(
        default_factory=lambda: int(time.time()),
        description="Unix timestamp when this session was obtained.",
    )
    latitude: float = Field(..., description="Geo header sent during auth.")
    longitude: float = Field(..., description="Geo header sent during auth.")
    client_id: str = Field(..., description="Public client id used at login.")

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def expires_at(self) -> int:
        """Unix timestamp when the access token expires."""
        return self.obtained_at + self.expires_in

    @property
    def seconds_remaining(self) -> int:
        """Seconds left before the access token expires (may be negative)."""
        return self.expires_at - int(time.time())

    @property
    def is_expired(self) -> bool:
        """True if the access token has expired (with a 30s safety margin)."""
        return self.seconds_remaining < 30

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: Path = DEFAULT_SESSION_PATH) -> Path:
        """Write the session to ``path`` with ``0600`` permissions.

        Creates the parent directory if needed (also ``0700``).
        Returns the absolute path written.
        """
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Write atomically: dump to tmp, then rename.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        return path.resolve()

    @classmethod
    def load(cls, path: Path = DEFAULT_SESSION_PATH) -> Session:
        """Read a previously-saved session.

        Raises FileNotFoundError if the file doesn't exist.
        """
        path = Path(path).expanduser()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    @classmethod
    def try_load(cls, path: Path = DEFAULT_SESSION_PATH) -> Session | None:
        """Like :meth:`load`, but returns ``None`` if the file is missing
        or unreadable.

        A missing file is the normal "first run" path and stays silent.
        Anything else (permissions, JSON corruption, schema mismatch from
        a stale session.json after a model bump) is logged so users have
        a hint when the CLI says "no session" but actually the file is
        broken.
        """
        try:
            return cls.load(path)
        except FileNotFoundError:
            return None
        except (ValueError, OSError) as exc:
            log.warning("session at %s is unreadable: %s", path, exc)
            return None
