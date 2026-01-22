# src/airpg/runtime/memory_stub.py
from __future__ import annotations
from typing import Dict, Any

"""
Minimal memory stub for AIRPG.

Memory is experience residue, not truth. It records markers of exposure,
salience, and instability — never facts, propositions, or resolved outcomes.

All memory is:
- Explicitly passed via state object
- Local to agent and session
- Optional and killable
- Non-authoritative
"""

# Key used to store memory in the state object
MEMORY_KEY = "memory"
MEMORY_ENABLED_KEY = "memory_enabled"


def memory_is_enabled(state: Dict[str, Any]) -> bool:
    """
    Returns True if memory is enabled in the given state.
    Memory is enabled by default unless explicitly disabled.
    """
    return state.get(MEMORY_ENABLED_KEY, True)


def memory_get_agent_bucket(state: Dict[str, Any], agent_id: str) -> Dict[str, int]:
    """
    Returns the memory bucket for a specific agent.
    Returns empty dict if memory is disabled or agent has no markers.
    """
    if not memory_is_enabled(state):
        return {}
    
    memory = state.get(MEMORY_KEY, {})
    return memory.get(agent_id, {})


def memory_record_marker(
    state: Dict[str, Any],
    agent_id: str,
    marker: str,
    intensity: int = 1
) -> None:
    """
    Records a memory marker for an agent.
    
    Markers are labels like: encountered, repeated, unstable_contradiction, salience.
    Intensity is clamped to >= 1.
    
    No-op if memory is disabled.
    """
    if not memory_is_enabled(state):
        return
    
    # Clamp intensity to >= 1
    intensity = max(1, intensity)
    
    # Initialize memory structure if needed
    if MEMORY_KEY not in state:
        state[MEMORY_KEY] = {}
    
    if agent_id not in state[MEMORY_KEY]:
        state[MEMORY_KEY][agent_id] = {}
    
    # Record or increment marker
    current = state[MEMORY_KEY][agent_id].get(marker, 0)
    state[MEMORY_KEY][agent_id][marker] = current + intensity


def memory_read_markers(state: Dict[str, Any], agent_id: str) -> Dict[str, int]:
    """
    Reads all memory markers for an agent.
    Returns empty dict if memory is disabled or agent has no markers.
    """
    return memory_get_agent_bucket(state, agent_id)
