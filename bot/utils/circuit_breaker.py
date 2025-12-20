"""Circuit breaker pattern for API calls."""
import asyncio
import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Open circuit after N failures
    success_threshold: int = 2  # Close circuit after N successes in half-open
    timeout: float = 60.0  # Time to wait before trying half-open (seconds)
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures


class CircuitBreaker:
    """Circuit breaker for protecting against failing services."""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.
        
        Args:
            name: Name of the circuit breaker
            config: Configuration options
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            # Check if we should attempt the call
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    log.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
                else:
                    raise Exception(f"Circuit breaker {self.name} is OPEN")
            elif self.state == CircuitState.HALF_OPEN:
                # Already in half-open, proceed
                pass
        
        # Attempt the call
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await self._on_success()
            return result
        except self.config.expected_exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    log.info(f"Circuit breaker {self.name} CLOSED after {self.success_count} successes")
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed in half-open, go back to open
                self.state = CircuitState.OPEN
                self.success_count = 0
                log.warning(f"Circuit breaker {self.name} OPENED after failure in HALF_OPEN")
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    log.warning(
                        f"Circuit breaker {self.name} OPENED after {self.failure_count} failures"
                    )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.timeout
    
    def reset(self):
        """Manually reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        log.info(f"Circuit breaker {self.name} manually reset")

