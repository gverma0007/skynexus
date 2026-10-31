"""Thread-safe generic TTL in-memory cache."""

from __future__ import annotations

import threading
import time
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Thread-safe in-memory cache with time-to-live expiration."""

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._value: T | None = None
        self._last_built: float = 0.0

    def get(self) -> T | None:
        with self._lock:
            if self._value is not None and (time.monotonic() - self._last_built) < self.ttl_seconds:
                return self._value
            return None

    def set(self, value: T) -> None:
        with self._lock:
            self._value = value
            self._last_built = time.monotonic()

    def get_or_set(self, builder: Callable[[], T]) -> T:
        with self._lock:
            if self._value is not None and (time.monotonic() - self._last_built) < self.ttl_seconds:
                return self._value
            value = builder()
            self._value = value
            self._last_built = time.monotonic()
            return value

    def invalidate(self) -> None:
        with self._lock:
            self._value = None
            self._last_built = 0.0

