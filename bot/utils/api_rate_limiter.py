"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Rate limiter for external API calls."""
import asyncio
import time
import logging
from collections import defaultdict
from typing import Dict, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 1.0  # Requests per second
    burst_size: int = 5  # Allow burst of N requests
    window_size: float = 60.0  # Time window in seconds


class APIRateLimiter:
    """Rate limiter for API calls using token bucket algorithm."""
    
    def __init__(self, name: str, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.
        
        Args:
            name: Name of the rate limiter
            config: Configuration options
        """
        self.name = name
        self.config = config or RateLimitConfig()
        self.tokens = self.config.burst_size
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """
        Acquire permission to make an API call.
        
        Returns:
            True if allowed, False if rate limited
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            tokens_to_add = elapsed * self.config.requests_per_second
            self.tokens = min(
                self.config.burst_size,
                self.tokens + tokens_to_add
            )
            self.last_update = now
            
            # Check if we have tokens
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            else:
                # Calculate wait time
                wait_time = (1.0 - self.tokens) / self.config.requests_per_second
                log.debug(f"Rate limited {self.name}, need to wait {wait_time:.2f}s")
                return False
    
    async def wait_if_needed(self):
        """Wait if rate limit is exceeded."""
        while not await self.acquire():
            wait_time = (1.0 - self.tokens) / self.config.requests_per_second
            await asyncio.sleep(min(wait_time, 1.0))  # Wait at most 1 second at a time


class GlobalAPIRateLimiter:
    """Global rate limiter manager for multiple APIs."""
    
    def __init__(self):
        """Initialize global rate limiter."""
        self.limiters: Dict[str, APIRateLimiter] = {}
        self._lock = asyncio.Lock()
    
    def get_limiter(self, api_name: str, config: Optional[RateLimitConfig] = None) -> APIRateLimiter:
        """
        Get or create rate limiter for an API.
        
        Args:
            api_name: Name of the API
            config: Optional configuration
            
        Returns:
            Rate limiter instance
        """
        if api_name not in self.limiters:
            self.limiters[api_name] = APIRateLimiter(api_name, config)
        return self.limiters[api_name]
    
    async def wait_for_api(self, api_name: str, config: Optional[RateLimitConfig] = None):
        """
        Wait for rate limit on an API.
        
        Args:
            api_name: Name of the API
            config: Optional configuration
        """
        limiter = self.get_limiter(api_name, config)
        await limiter.wait_if_needed()


# Global instance
_global_rate_limiter = GlobalAPIRateLimiter()


def get_api_rate_limiter() -> GlobalAPIRateLimiter:
    """Get global API rate limiter instance."""
    return _global_rate_limiter



