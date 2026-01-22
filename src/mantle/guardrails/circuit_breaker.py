# src/lms/guardrails/circuit_breaker.py
"""
Circuit Breaker Pattern

Prevents cascade failures and runaway AI calls by:
- Tracking failure rates
- "Opening" the circuit when failures exceed threshold
- Allowing gradual recovery with half-open state
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject all calls
    HALF_OPEN = "half_open" # Testing if service recovered


class CircuitOpen(Exception):
    """Raised when circuit is open and calls are rejected."""
    def __init__(self, message: str, retry_after: float):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    # How many failures before opening circuit
    failure_threshold: int = 5

    # How long to wait before trying again (seconds)
    recovery_timeout: float = 30.0

    # How many successes needed to close circuit from half-open
    success_threshold: int = 2

    # Window for counting failures (seconds)
    failure_window: float = 60.0

    # Timeout for individual calls (seconds)
    call_timeout: float = 30.0


class CircuitBreaker:
    """
    Circuit breaker for AI service calls.

    States:
    - CLOSED: Normal operation, calls go through
    - OPEN: Too many failures, all calls rejected immediately
    - HALF_OPEN: Testing recovery, limited calls allowed

    Usage:
        breaker = CircuitBreaker("gemini")

        # Before making a call
        if breaker.allow_request():
            try:
                result = await make_ai_call()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
                raise
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._lock = Lock()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._opened_at: float = 0
        self._failure_timestamps: list[float] = []

        logger.info(f"CircuitBreaker '{name}' initialized")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    def _clean_old_failures(self) -> None:
        """Remove failures outside the window."""
        now = time.time()
        cutoff = now - self.config.failure_window
        self._failure_timestamps = [
            t for t in self._failure_timestamps if t > cutoff
        ]
        self._failure_count = len(self._failure_timestamps)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            logger.warning(
                f"CircuitBreaker '{self.name}': {old_state.value} -> OPEN "
                f"(failures: {self._failure_count})"
            )
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            logger.info(f"CircuitBreaker '{self.name}': {old_state.value} -> HALF_OPEN")
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._failure_timestamps = []
            self._success_count = 0
            logger.info(f"CircuitBreaker '{self.name}': {old_state.value} -> CLOSED")

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed.

        Returns True if the request can proceed.
        Raises CircuitOpen if the circuit is open.
        """
        with self._lock:
            self._clean_old_failures()
            now = time.time()

            if self._state == CircuitState.CLOSED:
                return True

            elif self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                time_open = now - self._opened_at
                if time_open >= self.config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                else:
                    retry_after = self.config.recovery_timeout - time_open
                    raise CircuitOpen(
                        f"Circuit '{self.name}' is open. Service temporarily unavailable.",
                        retry_after=retry_after
                    )

            else:  # HALF_OPEN
                # Allow limited requests to test recovery
                return True

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            now = time.time()
            self._failure_timestamps.append(now)
            self._last_failure_time = now
            self._clean_old_failures()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        with self._lock:
            self._clean_old_failures()
            now = time.time()

            status = {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.config.failure_threshold,
            }

            if self._state == CircuitState.OPEN:
                time_open = now - self._opened_at
                status["time_until_retry"] = max(0, self.config.recovery_timeout - time_open)

            if self._state == CircuitState.HALF_OPEN:
                status["success_count"] = self._success_count
                status["success_threshold"] = self.config.success_threshold

            return status

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            logger.info(f"CircuitBreaker '{self.name}' manually reset")


class CircuitBreakerRegistry:
    """
    Registry of circuit breakers for different services.

    Usage:
        registry = CircuitBreakerRegistry()
        gemini_breaker = registry.get("gemini")
        neo4j_breaker = registry.get("neo4j")
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = Lock()

    def get(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker by name."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get_all_status(self) -> dict:
        """Get status of all circuit breakers."""
        with self._lock:
            return {
                name: breaker.get_status()
                for name, breaker in self._breakers.items()
            }

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()


# Global registry
_registry = CircuitBreakerRegistry()


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get a circuit breaker from the global registry."""
    return _registry.get(name, config)


def get_all_circuit_status() -> dict:
    """Get status of all circuit breakers."""
    return _registry.get_all_status()
