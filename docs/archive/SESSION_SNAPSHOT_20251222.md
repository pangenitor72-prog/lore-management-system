# AIRPG Session Snapshot — 2025-12-22

## Repository State

- **Branch:** `airpg-runtime-minimal`
- **Latest commit:** `c794be287c3e6d5ce9b65667aaea0c6c4cdd26ac`
- **Status:** Working tree clean, up to date with origin

## Sealed Phases Completed

- CP-1: Content Pressure (basic injection, determinism, non-authority)
- CP-2: Local Contradiction (coexisting atoms, no resolution)
- CP-3: Distributed Contradiction (multi-hop propagation, no collapse)
- CP-4: Topological Divergence (asymmetric exposure, halting as logic)
- Lore Ingestion Stub (claim-only, source-attributed, pressure adapter)
- Memory Stub (non-canon residue, killable, local-only)
- MP-1: Memory Integration Pressure (bias tendency, not possibility)

## Canonical Doctrine Documents

- `docs/airpg/CONTENT_PRESSURE_DOCTRINE.md`
- `docs/airpg/CONTENT_PRESSURE_CP2_DOCTRINE.md`
- `docs/airpg/CONTENT_PRESSURE_CP3_DOCTRINE.md`
- `docs/airpg/CONTENT_PRESSURE_CP4_DOCTRINE.md`

## CI Workflows (AIRPG Runtime)

- `airpg-runtime-invariant.yml` (core structural invariant)
- `airpg-runtime-sequential.yml`
- `airpg-runtime-session.yml`
- `airpg-runtime-gameplay.yml`
- `airpg-runtime-interface.yml`
- `airpg-runtime-content.yml` (CP-1)
- `airpg-runtime-content-cp2.yml`
- `airpg-runtime-content-cp3.yml`
- `airpg-runtime-content-cp4.yml`
- `airpg-runtime-lore-ingestion.yml`
- `airpg-runtime-memory.yml`
- `airpg-runtime-memory-integration.yml` (MP-1)

## Runtime Integrity

MinimalRuntime remains sealed and unmodified.

## Next Recommended Step

MP-2 (Memory Decay/Saturation) — optional

## Do Not Do

- Do not write canon from memory or lore systems
- Do not introduce persistence across runs
- Do not add authority, truth, or belief semantics
- Do not refactor MinimalRuntime
- Do not introduce global state or cross-session leakage
- Do not resolve contradictions automatically
