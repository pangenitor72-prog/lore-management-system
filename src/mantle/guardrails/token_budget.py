# src/lms/guardrails/token_budget.py
"""
Token Budget System

Prevents AI cost spirals by:
- Tracking token usage per session and globally
- Enforcing hard limits before calls are made
- Estimating costs before expensive operations
- Graceful degradation when limits are reached
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from threading import RLock
from enum import Enum

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    """Raised when token budget is exceeded."""
    def __init__(self, message: str, budget_type: str, used: int, limit: int):
        super().__init__(message)
        self.budget_type = budget_type
        self.used = used
        self.limit = limit


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, wait_seconds: float):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class BudgetTier(str, Enum):
    """Budget tiers for different use cases."""
    FREE = "free"           # Strict limits, demo mode
    STANDARD = "standard"   # Normal usage
    PREMIUM = "premium"     # Higher limits
    UNLIMITED = "unlimited" # No limits (admin/testing)


@dataclass
class TokenBudget:
    """
    Token budget configuration.

    Gemini 2.0 Flash pricing (as of 2024):
    - Input: $0.075 per 1M tokens
    - Output: $0.30 per 1M tokens

    For safety, we estimate higher.
    """
    # Per-request limits (Gemini 2.0 Flash has 1M context window)
    max_input_tokens_per_request: int = 32000   # Allow complex gameplay prompts
    max_output_tokens_per_request: int = 16000  # Allow detailed narrative responses

    # Per-session limits
    max_tokens_per_session: int = 400000   # ~400k tokens per session (doubled for longer sessions)
    max_requests_per_session: int = 200    # Max 200 AI calls per session

    # Hourly rate limits
    max_requests_per_hour: int = 60        # 1 per minute average
    max_tokens_per_hour: int = 100000      # 100k tokens/hour

    # Daily limits
    max_tokens_per_day: int = 500000       # 500k tokens/day
    max_requests_per_day: int = 500        # 500 requests/day

    # Cost limits (in USD)
    max_cost_per_session: float = 1.00     # $1 per session (doubled for longer sessions)
    max_cost_per_day: float = 5.00         # $5 per day

    # Pricing (USD per 1M tokens) - conservative estimates
    input_cost_per_million: float = 0.10   # $0.10 per 1M input
    output_cost_per_million: float = 0.40  # $0.40 per 1M output

    @classmethod
    def for_tier(cls, tier: BudgetTier) -> "TokenBudget":
        """Get budget configuration for a tier."""
        if tier == BudgetTier.FREE:
            return cls(
                max_tokens_per_session=10000,
                max_requests_per_session=20,
                max_requests_per_hour=10,
                max_tokens_per_hour=20000,
                max_tokens_per_day=50000,
                max_requests_per_day=50,
                max_cost_per_session=0.10,
                max_cost_per_day=0.50,
            )
        elif tier == BudgetTier.STANDARD:
            return cls()  # Default values
        elif tier == BudgetTier.PREMIUM:
            return cls(
                max_tokens_per_session=200000,
                max_requests_per_session=500,
                max_requests_per_hour=120,
                max_tokens_per_hour=500000,
                max_tokens_per_day=2000000,
                max_requests_per_day=2000,
                max_cost_per_session=2.00,
                max_cost_per_day=20.00,
            )
        else:  # UNLIMITED
            return cls(
                max_tokens_per_session=999999999,
                max_requests_per_session=999999,
                max_requests_per_hour=999999,
                max_tokens_per_hour=999999999,
                max_tokens_per_day=999999999,
                max_requests_per_day=999999,
                max_cost_per_session=9999.00,
                max_cost_per_day=9999.00,
            )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request."""
        input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_cost_per_million
        return input_cost + output_cost


@dataclass
class SessionUsage:
    """Track usage within a single session."""
    session_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    request_count: int = 0
    estimated_cost: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens


@dataclass
class HourlyUsage:
    """Track usage within the current hour."""
    hour_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0))
    total_tokens: int = 0
    request_count: int = 0


@dataclass
class DailyUsage:
    """Track usage within the current day."""
    day_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))
    total_tokens: int = 0
    request_count: int = 0
    total_cost: float = 0.0


class TokenTracker:
    """
    Tracks token usage and enforces budgets.

    Thread-safe for concurrent access.
    """

    def __init__(self, budget: Optional[TokenBudget] = None):
        self.budget = budget or TokenBudget()
        self._lock = RLock()  # Reentrant lock to avoid deadlock when nested methods acquire lock
        self._sessions: Dict[str, SessionUsage] = {}
        self._hourly = HourlyUsage()
        self._daily = DailyUsage()
        self._last_request_time: float = 0
        self._min_request_interval: float = 0.5  # 500ms between requests

        logger.info(f"TokenTracker initialized with budget: {self.budget.max_tokens_per_day} tokens/day")

    def _refresh_periods(self) -> None:
        """Reset hourly/daily counters if period has elapsed."""
        now = datetime.now(timezone.utc)

        # Check hourly reset
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        if current_hour > self._hourly.hour_start:
            self._hourly = HourlyUsage(hour_start=current_hour)

        # Check daily reset
        current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if current_day > self._daily.day_start:
            self._daily = DailyUsage(day_start=current_day)

    def get_session(self, session_id: str) -> SessionUsage:
        """Get or create session usage tracker."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionUsage(session_id=session_id)
            return self._sessions[session_id]

    def check_budget(
        self,
        session_id: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> Dict[str, Any]:
        """
        Check if a request is within budget BEFORE making the AI call.

        Returns a dict with:
        - allowed: bool
        - reason: str (if not allowed)
        - warnings: list of budget warnings
        - remaining: dict of remaining budgets

        Raises:
        - BudgetExceeded if hard limits are hit
        - RateLimitExceeded if rate limited
        """
        with self._lock:
            self._refresh_periods()

            session = self.get_session(session_id)
            estimated_total = estimated_input_tokens + estimated_output_tokens
            estimated_cost = self.budget.estimate_cost(estimated_input_tokens, estimated_output_tokens)

            warnings = []

            # Rate limiting - minimum time between requests
            now = time.time()
            time_since_last = now - self._last_request_time
            if time_since_last < self._min_request_interval:
                wait_time = self._min_request_interval - time_since_last
                raise RateLimitExceeded(
                    f"Rate limited. Please wait {wait_time:.1f}s",
                    wait_seconds=wait_time
                )

            # Check per-request limits
            if estimated_input_tokens > self.budget.max_input_tokens_per_request:
                raise BudgetExceeded(
                    f"Input too large: {estimated_input_tokens} tokens (max {self.budget.max_input_tokens_per_request})",
                    budget_type="request_input",
                    used=estimated_input_tokens,
                    limit=self.budget.max_input_tokens_per_request
                )

            # Check session limits
            if session.total_tokens + estimated_total > self.budget.max_tokens_per_session:
                raise BudgetExceeded(
                    f"Session token limit reached ({self.budget.max_tokens_per_session} tokens)",
                    budget_type="session_tokens",
                    used=session.total_tokens,
                    limit=self.budget.max_tokens_per_session
                )

            if session.request_count >= self.budget.max_requests_per_session:
                raise BudgetExceeded(
                    f"Session request limit reached ({self.budget.max_requests_per_session} requests)",
                    budget_type="session_requests",
                    used=session.request_count,
                    limit=self.budget.max_requests_per_session
                )

            if session.estimated_cost + estimated_cost > self.budget.max_cost_per_session:
                raise BudgetExceeded(
                    f"Session cost limit reached (${self.budget.max_cost_per_session:.2f})",
                    budget_type="session_cost",
                    used=int(session.estimated_cost * 100),
                    limit=int(self.budget.max_cost_per_session * 100)
                )

            # Check hourly limits
            if self._hourly.request_count >= self.budget.max_requests_per_hour:
                raise BudgetExceeded(
                    f"Hourly request limit reached ({self.budget.max_requests_per_hour})",
                    budget_type="hourly_requests",
                    used=self._hourly.request_count,
                    limit=self.budget.max_requests_per_hour
                )

            if self._hourly.total_tokens + estimated_total > self.budget.max_tokens_per_hour:
                raise BudgetExceeded(
                    f"Hourly token limit reached ({self.budget.max_tokens_per_hour})",
                    budget_type="hourly_tokens",
                    used=self._hourly.total_tokens,
                    limit=self.budget.max_tokens_per_hour
                )

            # Check daily limits
            if self._daily.request_count >= self.budget.max_requests_per_day:
                raise BudgetExceeded(
                    f"Daily request limit reached ({self.budget.max_requests_per_day})",
                    budget_type="daily_requests",
                    used=self._daily.request_count,
                    limit=self.budget.max_requests_per_day
                )

            if self._daily.total_tokens + estimated_total > self.budget.max_tokens_per_day:
                raise BudgetExceeded(
                    f"Daily token limit reached ({self.budget.max_tokens_per_day})",
                    budget_type="daily_tokens",
                    used=self._daily.total_tokens,
                    limit=self.budget.max_tokens_per_day
                )

            if self._daily.total_cost + estimated_cost > self.budget.max_cost_per_day:
                raise BudgetExceeded(
                    f"Daily cost limit reached (${self.budget.max_cost_per_day:.2f})",
                    budget_type="daily_cost",
                    used=int(self._daily.total_cost * 100),
                    limit=int(self.budget.max_cost_per_day * 100)
                )

            # Warnings for approaching limits
            session_token_pct = (session.total_tokens + estimated_total) / self.budget.max_tokens_per_session
            if session_token_pct > 0.8:
                warnings.append(f"Session at {session_token_pct*100:.0f}% of token budget")

            daily_token_pct = (self._daily.total_tokens + estimated_total) / self.budget.max_tokens_per_day
            if daily_token_pct > 0.8:
                warnings.append(f"Daily usage at {daily_token_pct*100:.0f}% of budget")

            return {
                "allowed": True,
                "warnings": warnings,
                "estimated_cost": estimated_cost,
                "remaining": {
                    "session_tokens": self.budget.max_tokens_per_session - session.total_tokens - estimated_total,
                    "session_requests": self.budget.max_requests_per_session - session.request_count - 1,
                    "hourly_requests": self.budget.max_requests_per_hour - self._hourly.request_count - 1,
                    "daily_tokens": self.budget.max_tokens_per_day - self._daily.total_tokens - estimated_total,
                }
            }

    def record_usage(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record actual token usage after a successful AI call."""
        with self._lock:
            self._refresh_periods()

            session = self.get_session(session_id)
            cost = self.budget.estimate_cost(input_tokens, output_tokens)
            total_tokens = input_tokens + output_tokens

            # Update session
            session.total_input_tokens += input_tokens
            session.total_output_tokens += output_tokens
            session.request_count += 1
            session.estimated_cost += cost

            # Update hourly
            self._hourly.total_tokens += total_tokens
            self._hourly.request_count += 1

            # Update daily
            self._daily.total_tokens += total_tokens
            self._daily.request_count += 1
            self._daily.total_cost += cost

            # Update last request time
            self._last_request_time = time.time()

            logger.debug(
                f"Recorded usage: session={session_id}, tokens={total_tokens}, "
                f"cost=${cost:.4f}, daily_total=${self._daily.total_cost:.4f}"
            )

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary."""
        with self._lock:
            self._refresh_periods()

            return {
                "hourly": {
                    "tokens": self._hourly.total_tokens,
                    "requests": self._hourly.request_count,
                    "tokens_remaining": self.budget.max_tokens_per_hour - self._hourly.total_tokens,
                    "requests_remaining": self.budget.max_requests_per_hour - self._hourly.request_count,
                },
                "daily": {
                    "tokens": self._daily.total_tokens,
                    "requests": self._daily.request_count,
                    "cost": round(self._daily.total_cost, 4),
                    "tokens_remaining": self.budget.max_tokens_per_day - self._daily.total_tokens,
                    "requests_remaining": self.budget.max_requests_per_day - self._daily.request_count,
                    "cost_remaining": round(self.budget.max_cost_per_day - self._daily.total_cost, 4),
                },
                "active_sessions": len(self._sessions),
                "budget_tier": "standard",
            }

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get usage summary for a specific session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {"exists": False}

            return {
                "exists": True,
                "session_id": session_id,
                "started_at": session.started_at.isoformat(),
                "total_tokens": session.total_tokens,
                "input_tokens": session.total_input_tokens,
                "output_tokens": session.total_output_tokens,
                "request_count": session.request_count,
                "estimated_cost": round(session.estimated_cost, 4),
                "tokens_remaining": self.budget.max_tokens_per_session - session.total_tokens,
                "requests_remaining": self.budget.max_requests_per_session - session.request_count,
            }

    def close_session(self, session_id: str) -> None:
        """Close a session and free its tracking data."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions.pop(session_id)
                logger.info(
                    f"Session {session_id} closed: {session.request_count} requests, "
                    f"{session.total_tokens} tokens, ${session.estimated_cost:.4f}"
                )


# Convenience function to estimate tokens from text
def estimate_tokens(text: str) -> int:
    """
    Rough token estimation.

    Rule of thumb: ~4 characters per token for English.
    This is conservative (overestimates slightly).
    """
    return len(text) // 3  # Slightly conservative
