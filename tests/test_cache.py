"""Tests for cache utility."""
import pytest
import asyncio
from bot.utils.cache import TTLCache


class TestTTLCache:
    """Test TTL cache."""
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self):
        """Test setting and getting from cache."""
        cache = TTLCache()
        await cache.set("test_key", "test_value")
        result = await cache.get("test_key", ttl=60)
        assert result == "test_value"
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cache expiration."""
        cache = TTLCache()
        await cache.set("test_key", "test_value")
        # Wait for expiration (with very short TTL)
        result = await cache.get("test_key", ttl=0)  # Expired immediately
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test clearing cache."""
        cache = TTLCache()
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        result1 = await cache.get("key1", ttl=60)
        result2 = await cache.get("key2", ttl=60)
        assert result1 is None
        assert result2 is None
    
    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Test deleting specific key."""
        cache = TTLCache()
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.delete("key1")
        result1 = await cache.get("key1", ttl=60)
        result2 = await cache.get("key2", ttl=60)
        assert result1 is None
        assert result2 == "value2"
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = TTLCache()
        stats = cache.get_stats()
        assert "total_entries" in stats
        assert "expired_entries" in stats
        assert "active_entries" in stats

