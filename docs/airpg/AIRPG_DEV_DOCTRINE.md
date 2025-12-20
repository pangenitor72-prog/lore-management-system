# AIRPG Development Doctrine

**Branch:** airpg-foundation
**Status:** Canonical
**Cutoff:** End of Phase 6D

---

## 1. Purpose

AIRPG is not a feature-first RPG system.

It is a **pressure-tested cognitive simulation engine** designed to prove that:
- belief
- personality
- conflict
- propagation
- termination
- saturation

can emerge **without shortcuts**.

This doctrine exists to prevent architectural drift, premature optimization, and hidden authority logic.

If a change contradicts this document, the change is invalid.

---

## 2. The Method: Pressure-First Development

AIRPG is built one pressure at a time.

Each phase:
- introduces **exactly one cognitive pressure**
- proves that behavior can emerge under **strict constraints**
- forbids compensating mechanisms

Only after proof is achieved may a mechanism be considered for runtime use.

Failure to prove emergence means the phase is incorrectly designed — not that the constraints should be relaxed.

---

## 3. Absolute Constraints (Non-Negotiable)

Unless a future phase explicitly proves otherwise, **NO PHASE MAY USE**:
- ❌ Memory or persistence
- ❌ Time advancement
- ❌ Randomness
- ❌ Weights or probabilistic scoring
- ❌ Counters or accumulators
- ❌ Hidden state
- ❌ Authority flags
- ❌ Player-exception logic
- ❌ Global knowledge shortcuts

If a behavior appears to require one of these, redesign the phase.

Do not smuggle mechanisms in “temporarily.”

---

## 4. Core Principles

### 4.1 Topology Is Law
- Information moves only through defined connections
- No omniscience
- No broadcast by default

### 4.2 Personality Governs Decisions
- Nodes decide based on their own dominant traits
- No external override of outcome logic
- No “source authority” shortcuts

### 4.3 Emergence Over Script
- Termination is emergent
- Saturation is emergent
- Conflict resolution is emergent

Nothing is hard-coded for narrative convenience.

### 4.4 The Player Is Not Special
- The player is a node
- The player has no privileged logic
- Any system that “helps the player” by exception is invalid

---

## 5. Locked Phases (DO NOT MODIFY)

### Phase 1–4C: FOUNDATION
**Status:** LOCKED
Proven:
- Deterministic personality engine
- Topology-constrained propagation
- Termination before saturation
- Full saturation when personalities allow
- No flooding
- No global knowledge

---

### Phase 5: PERSONALITY EDGE CASES
**Status:** LOCKED
Proven:
- Conflict resolution without authority flags
- Player treated as non-privileged node
- Personality alone determines response

---

### Phase 6: BELIEF DYNAMICS
**Status:** LOCKED (All Subphases)

#### 6A — Baseline Belief Resolution
- Personality determines belief conflict outcomes

#### 6B — Belief Inertia
- Externally injected belief-category labels bias outcomes
- No memory; bias supplied per run

#### 6C — Belief Interaction
- Documented separately if applicable
- Still no persistence, no weights

#### 6D — Source Credibility Pressure
- Source credibility pressure introduced
- Final outcomes still reduce to **receiver personality dominance**
- Any logic allowing source authority to override receiver was explicitly removed

**No phase in 6.x allows source authority to dictate outcome.**

---

## 6. Current Cutoff
**Development is paused safely at the end of Phase 6D.**

Anything beyond this point is exploratory and must not alter locked phases.

---

## 7. Agent Self-Audit Checklist (MANDATORY)
Before writing or modifying code, an agent must be able to answer “YES” to all:
- [ ] Does this phase introduce only one cognitive pressure?
- [ ] Can the behavior emerge without memory?
- [ ] Without randomness?
- [ ] Without authority flags?
- [ ] Without player exceptions?
- [ ] Does the final outcome reduce to node personality + topology?
- [ ] Does this avoid global knowledge?
- [ ] Does this preserve determinism?

If any answer is “NO” → stop.

---

## 8. Final Rule

AIRPG does not chase realism. AIRPG chases **proof**.

Belief must earn its power. Authority must emerge. Nothing is sacred except the constraints.
