"""Extension: a small on-disk cache for API responses, to keep traffic low.

Both providers ask clients to avoid repeated identical requests; MET Norway's
terms in particular expect caching until the time given in the Expires header.
Each entry is one JSON file named by a hash of the URL and parameters.
"""

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

__all__ = ["ResponseCache", "expiry_from_headers"]


def expiry_from_headers(headers: Mapping[str, str], now: float, default_ttl: float) -> float:
    """Unix time until which a response may be reused: the Expires header if present and valid,
    otherwise now + default_ttl."""
    expires = headers.get("Expires")
    if expires:
        try:
            return parsedate_to_datetime(expires).timestamp()
        except (TypeError, ValueError, IndexError):
            pass
    return now + default_ttl


class ResponseCache:
    """JSON response cache keyed by URL + parameters, with an expiry time per entry."""

    def __init__(self, directory: str | Path, default_ttl: float = 3600.0,
                 clock: Callable[[], float] = time.time) -> None:
        if default_ttl <= 0:
            raise ValueError("default_ttl must be positive")
        self.directory = Path(directory)
        self.default_ttl = default_ttl
        self.clock = clock
        self.hits = 0
        self.misses = 0

    def __repr__(self) -> str:
        return f"ResponseCache({str(self.directory)!r}, hits={self.hits}, misses={self.misses})"

    @staticmethod
    def key(url: str, params: Mapping[str, Any] | None) -> str:
        text = json.dumps({"url": url, "params": dict(params or {})}, sort_keys=True, default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    def _path(self, url: str, params: Mapping[str, Any] | None) -> Path:
        return self.directory / f"{self.key(url, params)}.json"

    def get(self, url: str, params: Mapping[str, Any] | None) -> Any | None:
        """Cached body if present and not expired, else None."""
        path = self._path(url, params)
        if path.exists():
            entry = json.loads(path.read_text(encoding="utf-8"))
            if entry["expires_at"] > self.clock():
                self.hits += 1
                return entry["body"]
        self.misses += 1
        return None

    def put(self, url: str, params: Mapping[str, Any] | None, body: Any,
            headers: Mapping[str, str] | None = None) -> float:
        """Store `body`; returns the expiry time used."""
        self.directory.mkdir(parents=True, exist_ok=True)
        expires_at = expiry_from_headers(headers or {}, self.clock(), self.default_ttl)
        entry = {"url": url, "params": dict(params or {}), "expires_at": expires_at, "body": body}
        self._path(url, params).write_text(json.dumps(entry, default=str), encoding="utf-8")
        return expires_at

    def clear(self) -> int:
        """Delete all entries; returns how many were removed."""
        removed = 0
        if self.directory.exists():
            for path in self.directory.glob("*.json"):
                path.unlink()
                removed += 1
        return removed
