"""Tests for rate limiting and circuit breaker."""

import asyncio
import pytest
from mcp_memoria.core.rate_limiter import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState,
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    ServiceRateLimiter,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self) -> None:
        """Test acquiring tokens within rate limit."""
        config = RateLimitConfig(max_requests=5, window_seconds=1.0)
        limiter = RateLimiter(config)

        # Should be able to acquire 5 tokens
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit(self) -> None:
        """Test acquiring tokens exceeds rate limit."""
        config = RateLimitConfig(max_requests=3, window_seconds=60.0)
        limiter = RateLimiter(config)

        # Acquire all tokens
        for _ in range(3):
            await limiter.acquire()

        # Next acquire should fail
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.acquire()

        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_try_acquire(self) -> None:
        """Test try_acquire returns boolean."""
        config = RateLimitConfig(max_requests=2, window_seconds=60.0)
        limiter = RateLimiter(config)

        assert await limiter.try_acquire() is True
        assert await limiter.try_acquire() is True
        assert await limiter.try_acquire() is False

    @pytest.mark.asyncio
    async def test_get_remaining(self) -> None:
        """Test getting remaining requests."""
        config = RateLimitConfig(max_requests=5, window_seconds=60.0)
        limiter = RateLimiter(config)

        assert limiter.get_remaining() == 5
        await limiter.acquire()
        assert limiter.get_remaining() == 4
        await limiter.acquire()
        assert limiter.get_remaining() == 3

    @pytest.mark.asyncio
    async def test_window_expiry(self) -> None:
        """Test that old requests expire from window."""
        config = RateLimitConfig(max_requests=2, window_seconds=0.1)
        limiter = RateLimiter(config)

        # Use up all tokens
        await limiter.acquire()
        await limiter.acquire()

        # Wait for window to expire
        await asyncio.sleep(0.15)

        # Should be able to acquire again
        await limiter.acquire()  # Should not raise


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_closed_state_allows_calls(self) -> None:
        """Test that closed circuit allows calls."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))

        async def success():
            return "ok"

        result = await cb.call(success)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_failures(self) -> None:
        """Test that circuit opens after threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=60.0)
        cb = CircuitBreaker("test", config)

        async def failing():
            raise ValueError("fail")

        # First failure
        with pytest.raises(ValueError):
            await cb.call(failing)
        assert cb.state == CircuitState.CLOSED

        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await cb.call(failing)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects(self) -> None:
        """Test that open circuit rejects calls."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        cb = CircuitBreaker("test", config)

        async def failing():
            raise ValueError("fail")

        # Open the circuit
        with pytest.raises(ValueError):
            await cb.call(failing)

        assert cb.state == CircuitState.OPEN

        # Next call should be rejected with CircuitOpenError
        with pytest.raises(CircuitOpenError) as exc_info:
            await cb.call(failing)

        assert exc_info.value.service == "test"
        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_half_open_recovery(self) -> None:
        """Test circuit transitions to half-open after timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        cb = CircuitBreaker("test", config)

        call_count = 0

        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise ValueError("fail")
            return "ok"

        # Open the circuit
        with pytest.raises(ValueError):
            await cb.call(failing_then_success)
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should transition to half-open and succeed
        result = await cb.call(failing_then_success)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self) -> None:
        """Test circuit reopens if half-open call fails."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        cb = CircuitBreaker("test", config)

        async def always_fail():
            raise ValueError("fail")

        # Open the circuit
        with pytest.raises(ValueError):
            await cb.call(always_fail)
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should fail and reopen circuit
        with pytest.raises(ValueError):
            await cb.call(always_fail)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_manual_reset(self) -> None:
        """Test manual circuit reset."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        cb = CircuitBreaker("test", config)

        async def failing():
            raise ValueError("fail")

        # Open the circuit
        with pytest.raises(ValueError):
            await cb.call(failing)
        assert cb.state == CircuitState.OPEN

        # Manual reset
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        """Test that success resets failure count."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=60.0)
        cb = CircuitBreaker("test", config)

        call_count = 0

        async def failing_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("fail")
            return "ok"

        # First call fails
        with pytest.raises(ValueError):
            await cb.call(failing_once)
        assert cb.state == CircuitState.CLOSED

        # Second call succeeds - should reset failure count
        await cb.call(failing_once)

        # Third call fails - but failure count was reset
        call_count = 0
        with pytest.raises(ValueError):
            await cb.call(failing_once)
        assert cb.state == CircuitState.CLOSED  # Still closed (only 1 failure)


class TestServiceRateLimiter:
    """Tests for ServiceRateLimiter combining rate limiting and circuit breaker."""

    @pytest.mark.asyncio
    async def test_combined_rate_limit_and_circuit(self) -> None:
        """Test that service limiter applies both rate limit and circuit breaker."""
        rate_config = RateLimitConfig(max_requests=5, window_seconds=60.0)
        circuit_config = CircuitBreakerConfig(failure_threshold=2)

        service = ServiceRateLimiter("test", rate_config, circuit_config)

        async def success():
            return "ok"

        # Should succeed
        result = await service.call(success)
        assert result == "ok"
        assert service.remaining_requests == 4
        assert service.circuit_state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_rate_limit_checked_first(self) -> None:
        """Test that rate limit is checked before circuit breaker."""
        rate_config = RateLimitConfig(max_requests=1, window_seconds=60.0)
        circuit_config = CircuitBreakerConfig(failure_threshold=10)

        service = ServiceRateLimiter("test", rate_config, circuit_config)

        async def success():
            return "ok"

        await service.call(success)

        # Rate limit should trigger before circuit breaker
        with pytest.raises(RateLimitExceeded):
            await service.call(success)
