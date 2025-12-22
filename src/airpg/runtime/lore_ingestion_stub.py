# src/airpg/runtime/lore_ingestion_stub.py
from __future__ import annotations


def ingest_lore_as_pressure(lore_text: str, source_label: str) -> str:
    """
    Converts lore input into a pressure-compatible string payload.

    This function:
    - Marks the content as a CLAIM (not fact)
    - Preserves the source label as metadata
    - Returns a single string suitable for CP-1 content injection
    - Performs NO persistence, NO memory writes, NO canon writes

    The output format is opaque to the runtime. It is simply a string
    that can be injected via existing content pathways.
    """
    return f"CLAIM|source={source_label}|{lore_text}"
