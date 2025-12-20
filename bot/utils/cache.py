"""TTL-based cache implementation with persistence."""
import time
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

log = logging.getLogger(__name__)


class TTLCache:
    """Thread-safe TTL cache with optional persistence."""
    
    def __init__(self, persistent_file: Optional[str] = None):
        """
        Initialize cache.
        
        Args:
            persistent_file: Optional path to JSON file for persistence
        """
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = asyncio.Lock()
        self._persistent_file = Path(persistent_file) if persistent_file else None
        
        # Load from disk if exists
        if self._persistent_file and self._persistent_file.exists():
            self._load_from_disk()

    def _load_from_disk(self):
        """Load cache from disk."""
        try:
            data = json.loads(self._persistent_file.read_text())
            current_time = time.time()
            for key, (timestamp, value) in data.items():
                # Only load non-expired entries
                if current_time - timestamp < 86400:  # 24 hours max
                    self._store[key] = (timestamp, value)
            log.info(f"Loaded {len(self._store)} entries from cache file")
        except Exception as e:
            log.warning(f"Failed to load cache from disk: {e}")

    def _save_to_disk(self):
        """Save cache to disk."""
        if not self._persistent_file:
            return
        
        try:
            # Convert to serializable format
            data = {k: [ts, v] for k, (ts, v) in self._store.items()}
            self._persistent_file.parent.mkdir(parents=True, exist_ok=True)
            self._persistent_file.write_text(json.dumps(data, default=str))
        except Exception as e:
            log.warning(f"Failed to save cache to disk: {e}")

    async def get(self, key: str, ttl: int) -> Any:
        """
        Get value from cache if it exists and hasn't expired.
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
            
        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            ts, val = self._store.get(key, (0, None))
            if val is not None and time.time() - ts < ttl:
                return val
            # Remove expired entry
            if key in self._store:
                del self._store[key]
            return None

    async def set(self, key: str, value: Any, save_to_disk: bool = True) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            save_to_disk: Whether to persist to disk immediately
        """
        async with self._lock:
            self._store[key] = (time.time(), value)
            if save_to_disk and self._persistent_file:
                # Save to disk asynchronously
                asyncio.create_task(asyncio.to_thread(self._save_to_disk))

    async def clear(self) -> None:
        """Clear all cached values."""
        async with self._lock:
            self._store.clear()
            if self._persistent_file:
                asyncio.create_task(asyncio.to_thread(self._save_to_disk))

    async def delete(self, key: str) -> None:
        """
        Delete a specific key from cache.
        
        Args:
            key: Cache key to delete
        """
        async with self._lock:
            if key in self._store:
                del self._store[key]
                if self._persistent_file:
                    asyncio.create_task(asyncio.to_thread(self._save_to_disk))

    async def cleanup_expired(self, ttl: int) -> int:
        """
        Remove expired entries from cache.
        
        Args:
            ttl: Time to live threshold
            
        Returns:
            Number of entries removed
        """
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (ts, _) in self._store.items()
                if current_time - ts >= ttl
            ]
            for key in expired_keys:
                del self._store[key]
            
            if expired_keys and self._persistent_file:
                asyncio.create_task(asyncio.to_thread(self._save_to_disk))
            
            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        current_time = time.time()
        total = len(self._store)
        expired = sum(1 for ts, _ in self._store.values() if current_time - ts >= 86400)
        
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired
        }
