# src/airpg/runtime/ephemeral_memory.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

@dataclass(frozen=True)
class MemoryWriteResult:
    wrote: bool
    reason: str

class EphemeralMemory:
    """
    One-slot, write-once, interaction-scoped memory.
    """
    def __init__(self) -> None:
        self._slot: Dict[str, Optional[str]] = {}
        self._written: Dict[str, bool] = {}

    def begin_interaction(self, agent_ids: Tuple[str, ...]) -> None:
        # Hard reset boundary
        self._slot = {aid: None for aid in agent_ids}
        self._written = {aid: False for aid in agent_ids}

    def write_once(self, agent_id: str, value: str) -> MemoryWriteResult:
        if agent_id not in self._slot:
            return MemoryWriteResult(False, "unknown_agent")
        if self._written[agent_id]:
            return MemoryWriteResult(False, "already_written")

        self._slot[agent_id] = value
        self._written[agent_id] = True
        return MemoryWriteResult(True, "ok")

    def read(self, agent_id: str) -> Optional[str]:
        return self._slot.get(agent_id)

    def snapshot(self) -> Dict[str, Optional[str]]:
        # Required: explicit visibility
        return dict(self._slot)
