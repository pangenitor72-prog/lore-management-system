# src/airpg/runtime/runtime.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any, Callable

from .ephemeral_memory import EphemeralMemory

@dataclass
class TraceEvent:
    step: int
    receiver: str
    sender: Optional[str]
    message: str
    memory_before: Optional[str]
    memory_write: Dict[str, Any]
    memory_after: Optional[str]


class MinimalRuntime:
    """
    Runtime wrapper that introduces ephemeral memory
    without altering proven decision logic.
    """

    def __init__(self) -> None:
        self.memory = EphemeralMemory()

    def run_interaction(
        self,
        agent_ids: Tuple[str, ...],
        deliver_fn: Callable[..., List[Tuple[str, str]]],
        initial_receiver: str,
        initial_message: str,
        initial_sender: Optional[str] = None,
        max_steps: int = 200,
    ) -> List[TraceEvent]:
        """
        One interaction = one input + full deterministic cascade.
        Memory is wiped before and after.
        """
        self.memory.begin_interaction(agent_ids)

        trace: List[TraceEvent] = []
        queue: List[Tuple[Optional[str], str, str]] = [
            (initial_sender, initial_receiver, initial_message)
        ]

        step = 0
        while queue and step < max_steps:
            sender, receiver, message = queue.pop(0)

            mem_before = self.memory.read(receiver)
            write_result = self.memory.write_once(
                receiver, f"heard:{message[:64]}"
            )
            mem_after = self.memory.read(receiver)

            # CRITICAL: deliver_fn MUST ignore memory entirely
            forwards = deliver_fn(
                receiver=receiver,
                sender=sender,
                message=message,
            )

            trace.append(
                TraceEvent(
                    step=step,
                    receiver=receiver,
                    sender=sender,
                    message=message,
                    memory_before=mem_before,
                    memory_write={
                        "wrote": write_result.wrote,
                        "reason": write_result.reason,
                    },
                    memory_after=mem_after,
                )
            )

            for next_receiver, next_message in forwards:
                queue.append((receiver, next_receiver, next_message))

            step += 1

        return trace
