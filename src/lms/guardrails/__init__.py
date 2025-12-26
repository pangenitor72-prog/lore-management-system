# src/lms/guardrails/__init__.py
"""
Guardrails Module

Prevents AI cost spirals and ensures sustainable operation:
- Token budgets per session and globally
- Rate limiting
- Circuit breakers for runaway calls
- Cost estimation and tracking
"""

from .token_budget import (
    TokenBudget,
    TokenTracker,
    BudgetExceeded,
    RateLimitExceeded,
)
from .circuit_breaker import CircuitBreaker, CircuitOpen

__all__ = [
    "TokenBudget",
    "TokenTracker",
    "BudgetExceeded",
    "RateLimitExceeded",
    "CircuitBreaker",
    "CircuitOpen",
]
