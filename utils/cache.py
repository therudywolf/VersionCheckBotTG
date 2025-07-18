"""Thread‑safe in‑memory TTL cache (async‑ready)."""
import asyncio
import time
from typing import Any, Dict, Tuple

class TTLCache:
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str, ttl: int) -> Any | None:
        async with self._lock:
            ts, val = self._store.get(key, (0, None))
            if val is not None and time.time() - ts < ttl:
                return val
            return None

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._store[key] = (time.time(), value)
