# src/airpg/runtime/memory_integration_pressure.py
from __future__ import annotations
from typing import Dict, Any, List, TypeVar

from .memory_stub import memory_is_enabled, memory_read_markers

"""
MP-1: Memory Integration Pressure

This module proves that memory can bias TENDENCY without constraining POSSIBILITY.

Rules:
- Bias is explicit, optional, and killable.
- Bias affects ordering of already-legal options only.
- Bias does not filter, add, or resolve.
- Bias is deterministic.
"""

T = TypeVar("T")

# Allowed markers that may influence bias
ALLOWED_MARKERS = frozenset({"encountered", "repeated", "salience"})


def apply_memory_bias(
    state: Dict[str, Any],
    agent_id: str,
    options: List[T]
) -> List[T]:
    """
    Applies a deterministic memory-based bias to a list of options.

    Args:
        state: The session state containing memory (if enabled).
        agent_id: The agent whose memory to consult.
        options: A list of already-legal options (opaque objects or strings).

    Returns:
        A NEW list with potentially reordered options.
        - If memory is disabled: returns options unchanged (as new list).
        - If no relevant markers exist: returns options unchanged (as new list).
        - If markers exist: applies deterministic reordering.

    Guarantees:
        - Output contains exactly the same elements as input (no filtering).
        - Output length equals input length.
        - Deterministic: same inputs yield same outputs.
        - No side effects.
    """
    # Always return a new list, never mutate input
    if not options:
        return list(options)

    # If memory is disabled, return unchanged copy
    if not memory_is_enabled(state):
        return list(options)

    # Read markers for this agent
    markers = memory_read_markers(state, agent_id)

    # Filter to only allowed markers
    relevant_markers = {k: v for k, v in markers.items() if k in ALLOWED_MARKERS}

    # If no relevant markers, return unchanged copy
    if not relevant_markers:
        return list(options)

    # Calculate a bias score based on markers
    # This is a simple, deterministic formula:
    # Higher salience + repeated exposure = stronger bias toward front
    bias_score = (
        relevant_markers.get("salience", 0) +
        relevant_markers.get("repeated", 0) * 2 +
        relevant_markers.get("encountered", 0)
    )

    # If bias_score is 0, no reordering needed
    if bias_score == 0:
        return list(options)

    # Apply deterministic reordering:
    # Rotate the list by (bias_score mod len) positions
    # This biases toward different positions based on memory state
    # but NEVER removes or adds elements
    n = len(options)
    rotation = bias_score % n

    # Create new rotated list
    result = list(options[rotation:]) + list(options[:rotation])

    return result
