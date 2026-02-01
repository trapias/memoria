"""Rate limiting and circuit breaker for external services."""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests: int = 100  # Maximum requests per window
    window_seconds: float = 60.0  # Time window in seconds
    burst_limit: int = 10  # Maximum burst size


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening circuit
    recovery_timeout: float = 30.0  # Seconds before trying half-open
    success_threshold: int = 2  # Successes needed to close from half-open


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.1f}s")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, service: str, retry_after: float):
        self.service = service
        self.retry_after = retry_after
        super().__init__(f"Circuit open for {service}. Retry after {retry_after:.1f}s")


@dataclass
class RateLimiter:
    """Token bucket rate limiter with sliding window."""

    config: RateLimitConfig = field(default_factory=RateLimitConfig)
    _timestamps: deque = field(default_factory=deque, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def _cleanup_old_timestamps(self) -> None:
        """Remove timestamps outside the current window."""
        cutoff = time.monotonic() - self.config.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    async def acquire(self) -> None:
        """Acquire a rate limit token. Raises RateLimitExceeded if limit reached."""
        async with self._lock:
            self._cleanup_old_timestamps()

            if len(self._timestamps) >= self.config.max_requests:
                # Calculate retry time based on oldest request
                oldest = self._timestamps[0]
                retry_after = oldest + self.config.window_seconds - time.monotonic()
                raise RateLimitExceeded(max(0.1, retry_after))

            self._timestamps.append(time.monotonic())

    async def try_acquire(self) -> bool:
        """Try to acquire a token without raising. Returns True if acquired."""
        try:
            await self.acquire()
            return True
        except RateLimitExceeded:
            return False

    def get_remaining(self) -> int:
        """Get remaining requests in current window."""
        self._cleanup_old_timestamps()
        return max(0, self.config.max_requests - len(self._timestamps))


@dataclass
class CircuitBreaker:
    """Circuit breaker for external service calls."""

    name: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    async def _check_recovery(self) -> None:
        """Check if circuit should transition to half-open."""
        if self._state == CircuitState.OPEN:
            time_since_failure = time.monotonic() - self._last_failure_time
            if time_since_failure >= self.config.recovery_timeout:
                logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN (attempting recovery)")
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Exception: Original exception from func if circuit allows
        """
        async with self._lock:
            await self._check_recovery()

            if self._state == CircuitState.OPEN:
                retry_after = (
                    self.config.recovery_timeout
                    - (time.monotonic() - self._last_failure_time)
                )
                raise CircuitOpenError(self.name, max(0.1, retry_after))

        try:
            result = await func(*args, **kwargs)

            async with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._success_count += 1
                    if self._success_count >= self.config.success_threshold:
                        logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED (recovered)")
                        self._state = CircuitState.CLOSED
                        self._failure_count = 0
                elif self._state == CircuitState.CLOSED:
                    # Reset failure count on success
                    self._failure_count = 0

            return result

        except Exception as e:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.monotonic()

                if self._state == CircuitState.HALF_OPEN:
                    logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (recovery failed)")
                    self._state = CircuitState.OPEN
                elif (
                    self._state == CircuitState.CLOSED
                    and self._failure_count >= self.config.failure_threshold
                ):
                    logger.warning(
                        f"Circuit {self.name}: CLOSED -> OPEN "
                        f"(failures: {self._failure_count})"
                    )
                    self._state = CircuitState.OPEN

            raise

    def reset(self) -> None:
        """Manually reset circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        logger.info(f"Circuit {self.name}: manually reset to CLOSED")


class ServiceRateLimiter:
    """Combined rate limiter and circuit breaker for a service."""

    def __init__(
        self,
        name: str,
        rate_config: RateLimitConfig | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
    ):
        """Initialize service rate limiter.

        Args:
            name: Service name for logging
            rate_config: Rate limiting configuration
            circuit_config: Circuit breaker configuration
        """
        self.name = name
        self.rate_limiter = RateLimiter(rate_config or RateLimitConfig())
        self.circuit_breaker = CircuitBreaker(name, circuit_config or CircuitBreakerConfig())

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with rate limiting and circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            RateLimitExceeded: If rate limit is exceeded
            CircuitOpenError: If circuit is open
            Exception: Original exception from func
        """
        # Check rate limit first
        await self.rate_limiter.acquire()

        # Then check circuit breaker
        return await self.circuit_breaker.call(func, *args, **kwargs)

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.circuit_breaker.state

    @property
    def remaining_requests(self) -> int:
        """Get remaining requests in current rate limit window."""
        return self.rate_limiter.get_remaining()


# Default configurations for Memoria services
OLLAMA_RATE_CONFIG = RateLimitConfig(
    max_requests=100,
    window_seconds=60.0,
    burst_limit=10,
)

OLLAMA_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=1,
)

QDRANT_RATE_CONFIG = RateLimitConfig(
    max_requests=500,
    window_seconds=60.0,
    burst_limit=50,
)

QDRANT_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=15.0,
    success_threshold=2,
)

STORE_RATE_CONFIG = RateLimitConfig(
    max_requests=100,
    window_seconds=60.0,
    burst_limit=10,
)
