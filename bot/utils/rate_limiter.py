"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
"""Rate limiting utilities."""
import time
import asyncio
from collections import defaultdict
from typing import Dict, Tuple, Optional

from bot.utils.constants import (
    SECONDS_PER_MINUTE,
    SECONDS_PER_HOUR
)


class RateLimiter:
    """Rate limiter for user requests."""
    
    def __init__(
        self,
        requests_per_minute: int = 20,
        requests_per_hour: int = 200
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            requests_per_hour: Maximum requests per hour
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self._minute_requests: Dict[int, list] = defaultdict(list)
        self._hour_requests: Dict[int, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if request is allowed for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        async with self._lock:
            current_time = time.time()
            
            # Clean old requests
            self._clean_old_requests(user_id, current_time)
            
            # Check minute limit
            if len(self._minute_requests[user_id]) >= self.requests_per_minute:
                return False, f"Превышен лимит запросов ({self.requests_per_minute} в минуту). Подождите немного."
            
            # Check hour limit
            if len(self._hour_requests[user_id]) >= self.requests_per_hour:
                return False, f"Превышен лимит запросов ({self.requests_per_hour} в час). Подождите немного."
            
            # Record request
            self._minute_requests[user_id].append(current_time)
            self._hour_requests[user_id].append(current_time)
            
            return True, None
    
    def _clean_old_requests(self, user_id: int, current_time: float):
        """Clean old requests outside the time windows."""
        minute_cutoff = current_time - SECONDS_PER_MINUTE
        self._minute_requests[user_id] = [
            ts for ts in self._minute_requests[user_id] if ts > minute_cutoff
        ]
        
        hour_cutoff = current_time - SECONDS_PER_HOUR
        self._hour_requests[user_id] = [
            ts for ts in self._hour_requests[user_id] if ts > hour_cutoff
        ]
    
    async def get_remaining(self, user_id: int) -> Dict[str, int]:
        """
        Get remaining requests for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with remaining requests
        """
        async with self._lock:
            current_time = time.time()
            self._clean_old_requests(user_id, current_time)
            
            return {
                "minute": max(0, self.requests_per_minute - len(self._minute_requests[user_id])),
                "hour": max(0, self.requests_per_hour - len(self._hour_requests[user_id]))
            }


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance, initialized from config."""
    global _rate_limiter
    if _rate_limiter is None:
        from config import settings
        _rate_limiter = RateLimiter(
            requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            requests_per_hour=settings.RATE_LIMIT_PER_HOUR
        )
    return _rate_limiter
