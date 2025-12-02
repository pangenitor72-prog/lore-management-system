# **`.cursor/rules.md` — FULL INTEGRATED VERSION**

```markdown
# Cursor Project Rules – LMS / MANTLE

**Version:** 2.0 (Integrated)  
**Last Updated:** 2025-12-01  
**Authority:** Shawn King

You are an AI assistant working inside Cursor on the LMS / MANTLE codebase.

**Your primary goals:**
1. Preserve the existing architecture
2. Respect subsystem boundaries
3. Implement changes in small, explicit diffs
4. Follow the project's subsystem implementation templates

This file defines **global rules for ALL work in this repo**.

---

## 1. Global Safety Rules

### 1.1 Core Safety Principles

**DO NOT:**
- Refactor multiple subsystems in a single operation
- Move files or rename modules unless explicitly instructed
- Introduce new external dependencies without explicit approval
- Rewrite large files unless absolutely necessary and clearly justified

**DO:**
- Prefer minimal diffs over full-file rewrites
- Make the smallest, safest change that solves the current task
- Preserve structure, contracts, and intent

### 1.2 Large Refactor Protocol

If you believe a large refactor is needed:
1. **STOP immediately**
2. **EXPLAIN** why in plain language
3. **PROPOSE** alternatives
4. **WAIT** for explicit approval before proceeding

### 1.3 Forbidden Actions (Absolute)

These actions are **NEVER ALLOWED** without explicit human override:

**Architectural Changes:**
- ❌ Creating new subsystems
- ❌ Merging existing subsystems
- ❌ Changing subsystem purpose or boundaries
- ❌ Violating dependency direction (see section 6.2)
- ❌ Creating circular dependencies

**Breaking Changes:**
- ❌ Renaming public APIs
- ❌ Changing function signatures without backward compatibility
- ❌ Deleting modules currently in use
- ❌ Modifying core infrastructure (Entity Factory, OCEAN, Neo4j Adapter) without approval

**Scope Creep:**
- ❌ Adding features not in specification
- ❌ "Improving" code not currently being worked on
- ❌ Optimizing without documented performance problem
- ❌ Refactoring "for style" or "for consistency"

**Data Loss Risks:**
- ❌ Deleting database nodes without migration plan
- ❌ Changing schema without migration plan
- ❌ Dropping tables/collections
- ❌ Modifying production data

**Hidden Complexity:**
- ❌ Hidden LLM calls outside orchestrators
- ❌ Hidden API calls in utility functions
- ❌ Hidden state mutations
- ❌ Hidden side effects in "pure" functions

---

## 2. Subsystem Implementation Rules

### 2.1 Implementation Contracts

For any subsystem (e.g., Smart Ingestor, Decoherence Engine, Query Layer), look for its implementation contract in:
- `docs/UNIVERSAL_IMPLEMENTATION_PROMPT.md`, or
- `src/<subsystem>/SUBSYSTEM_CONTRACT.md`, or
- `docs/<subsystem>_DESIGN.md`

**Follow exactly:**
- The defined directory structure
- The module implementation order
- The public API contracts
- The integration rules
- The allowed/forbidden imports

If a Master Implementation Prompt is provided:
- **Treat it as law for that subsystem**
- Do NOT invent new architecture
- Do NOT cross boundaries

### 2.2 First Response Rule (MANDATORY)

When starting **ANY** new subsystem or major feature, your **first response must contain ZERO CODE**.

**Required First Response Structure:**

```
1. REPO SCAN SUMMARY
   - Files belonging to this subsystem
   - Dependencies identified
   - Conflicts with existing code
   - Integration points with other subsystems

2. IMPLEMENTATION PLAN
   - Module 1: [name, purpose, file path, dependencies]
   - Module 2: [name, purpose, file path, dependencies]
   - Module N: [name, purpose, file path, dependencies]
   - Estimated order of implementation

3. CONFIRMATION
   "WAITING FOR APPROVAL TO BEGIN MODULE 1. NO CODE GENERATED."
```

**You may NOT:**
- Generate code in first response
- Skip repo scanning
- Assume architecture without verification
- Proceed without explicit approval

### 2.3 Module-by-Module Development (MANDATORY)

You must implement **EXACTLY ONE module per response**.

**Workflow:**
1. Human: "Approved, build module 1: format_detector.py"
2. AI: [Generates ONLY format_detector.py with minimal diff]
3. AI: [Updates handoff dossier]
4. AI: "Module 1 complete. Waiting for approval to proceed to module 2."
5. Human: "Approved, proceed to module 2"
6. [Repeat]

**You may NOT:**
- Generate multiple modules in a single response
- Skip ahead to later modules without approval
- Combine modules without permission

**Exception:** If explicitly told "generate all modules", you may proceed, but you must still:
- Generate in correct order
- Update handoff dossier after each module
- Pause if context becomes constrained

---

## 3. File-Scoped Changes & Diff Discipline

### 3.1 Minimal Diff Principle

When editing a file:
- **ONLY** change what is needed for the current task
- Do NOT edit unrelated functions "while you are there"
- Do NOT reformat code "for style" without permission
- Keep behavior-preserving cleanups small and localized

### 3.2 Preferred Strategies

**Prefer:**
- Adding new functions instead of reorganizing entire files
- Adding new modules instead of merging modules together
- Extending existing classes instead of rewriting them
- All changes expressed as minimal diffs

**Avoid:**
- Full-file rewrites
- Large-scale reorganization
- Unnecessary whitespace changes
- Import reordering without purpose

### 3.3 Full-File Rewrite Protocol

If you **must** rewrite an entire file:
1. **State:** "This requires a full-file rewrite."
2. **Explain:** Provide clear justification
3. **Show:** Expected before/after structure
4. **Wait:** For confirmation before proceeding

**Valid reasons for rewrite:**
- File has fundamental structural flaw
- Technical debt is blocking progress
- Security vulnerability requires complete revision

**Invalid reasons:**
- "The code could be more elegant"
- "I think a different pattern would be better"
- "This would be easier to read if..."

---

## 4. Orchestrator / LLM Call Rules

### 4.1 LLM Call Centralization (CRITICAL)

For subsystems that use LLMs (e.g., Smart Ingestor, Decoherence Engine):

**RULE:** **Only the orchestrator module may call LLMs.**

**All other modules must be pure functions:**
- No network calls
- No filesystem writes (except logging)
- No database operations
- No LLM API calls
- No external HTTP requests

**Why this matters:**
- Prevents hidden API costs
- Ensures deterministic behavior in testable code
- Makes debugging possible
- Prevents context leakage

### 4.2 Pure Function Requirements

```python
# ✅ CORRECT: Pure transformation
def infer_personality_from_text(description: str) -> dict:
    # Parse description, apply rules, return OCEAN traits
    if "barked orders" in description:
        conscientiousness = 0.9
    # ... more logic
    return {"openness": 0.7, "conscientiousness": 0.9, ...}

# ❌ WRONG: Hidden side effects
def infer_personality_from_text(description: str) -> dict:
    result = requests.post("https://api.openai.com/...", ...)  # FORBIDDEN
    db.store(result)  # FORBIDDEN
    logger.critical("Processing!")  # FORBIDDEN (excessive logging)
    return result
```

### 4.3 Adding New LLM Behavior

If you need new LLM functionality:
1. Add it to the **orchestrator layer only**
2. Use clearly defined request/response data structures
3. Document the LLM call purpose and expected output
4. Add error handling for API failures
5. Update subsystem contract with new capability

---

## 5. Context / Pipeline Rules

### 5.1 Pipeline-Based Subsystems

For pipeline-based subsystems (e.g., Smart Ingestor with multi-pass extraction):

**Each pass may ONLY:**
- **Read** keys documented as outputs from earlier passes
- **Write** keys documented as its own outputs
- Follow the defined pass order

**Each pass may NOT:**
- Read keys from passes that haven't run yet
- Overwrite keys owned by other passes
- Skip required passes
- Reorder passes without contract update

### 5.2 Context Key Management

**DO NOT:**
- Invent new context keys without updating the subsystem contract
- Use undocumented keys
- Assume keys exist without validation
- Modify context structure without approval

**When in doubt:**
- Update the subsystem's contract document first
- Get approval for new context keys
- Document key purpose and data type

### 5.3 Pipeline Example (Smart Ingestor)

```python
# Pass 1: Format Detection
context["document_format"] = "faction_dossier"  # ✅ Writes its key

# Pass 2: Entity Extraction  
doc_format = context["document_format"]  # ✅ Reads from Pass 1
context["raw_entities"] = [...]  # ✅ Writes its key

# Pass 3: Enrichment
entities = context["raw_entities"]  # ✅ Reads from Pass 2
context["enriched_entities"] = [...]  # ✅ Writes its key

# ❌ WRONG: Pass 2 reads from Pass 3
entities = context["enriched_entities"]  # FORBIDDEN - future pass
```

---

## 6. Subsystem Boundaries

### 6.1 Subsystem Organization

You must respect these subsystem boundaries:

```
src/
├── smart_ingestor/      [AI document ingestion → Neo4j]
├── decoherence_engine/  [Temporal simulation / state resolution]
├── query_engine/        [Semantic search + filtered truth]
├── mantle_runtime/      [AIRPG game master runtime]
├── entity_factory/      [Entity templates + validation] — CORE
├── ocean_personality/   [NPC personality system] — CORE
├── neo4j_adapter/       [Database interface] — CORE
├── auditor/             [Contradiction detection / validation]
├── api/                 [API layer / endpoints]
└── ui/                  [Presentation layer / templates]
```

**Subsystem Types:**
- **Subsystems:** Smart Ingestor, Decoherence Engine, Query Engine, MANTLE Runtime
- **Core Infrastructure:** Entity Factory, OCEAN Personality, Neo4j Adapter
- **Support:** Auditor, API, UI

### 6.2 Dependency Direction (GOLDEN RULE)

**Fundamental Principle:**  
**Low-level modules may depend on high-level modules, NEVER the reverse.**

This is called the **Dependency Inversion Principle** and is **non-negotiable**.

**✅ ALLOWED (Correct Direction):**
```python
# Higher-level depends on lower-level
from src.entity_factory import EntityFactory  # Smart Ingestor → Factory ✅
from src.neo4j_adapter import Neo4jAdapter    # Decoherence → Database ✅
from src.query_engine import QueryEngine      # MANTLE → Query ✅
```

**❌ FORBIDDEN (Reverse Dependencies):**
```python
# Lower-level depends on higher-level
from src.smart_ingestor import SmartIngestor  # Factory → Ingestor ❌
from src.decoherence_engine import Engine     # Database → Decoherence ❌
from src.mantle_runtime import Runtime        # Query → MANTLE ❌
```

**Dependency Hierarchy (Low → High):**
```
[Level 1] Neo4j Adapter, Entity Factory, OCEAN
    ↓ (may be imported by)
[Level 2] Smart Ingestor, Decoherence Engine, Auditor
    ↓ (may be imported by)
[Level 3] Query Engine
    ↓ (may be imported by)
[Level 4] MANTLE Runtime
    ↓ (may be imported by)
[Level 5] API Layer
    ↓ (may be imported by)
[Level 6] UI Layer
```

**Before adding ANY import:**
1. Verify it respects dependency direction
2. If unclear, **ASK HUMAN**
3. Never create circular dependencies
4. If you need reverse dependency, use **adapter pattern** or **event system**

### 6.3 Cross-Boundary Communication

**DO NOT:**
- Import from a subsystem higher in the hierarchy
- Push domain logic down into generic layers (e.g., database adapters)
- Create tight coupling between subsystems

**DO:**
- Use orchestrators as public entry points
- Pass data through well-defined interfaces
- Use dependency injection for flexibility

---

## 7. LoreIngestor / EntityFactory / OCEAN Protection

### 7.1 Protected Core Infrastructure

These modules are **CORE INFRASTRUCTURE** and must not be modified without explicit approval:

**Entity Factory:**
```
src/entity_factory/
├── factory.py           [IMMUTABLE without approval]
├── templates.py         [IMMUTABLE without approval]
└── validators.py        [IMMUTABLE without approval]
```

**OCEAN Personality System:**
```
src/ocean_personality/
├── personality.py       [IMMUTABLE without approval]
├── traits.py            [IMMUTABLE without approval - trait definitions]
└── generators.py        [Extensible with approval]
```

**Neo4j Adapter:**
```
src/neo4j_adapter/
├── adapter.py           [IMMUTABLE without approval]
├── queries.py           [Extensible with approval]
└── schema.py            [PROTECTED - schema changes require migration]
```

### 7.2 Allowed Modifications

**Entity Factory - Allowed:**
- Adding new entity types (with approval and contract update)
- Extending validation rules (with approval)
- Adding new templates (following existing pattern)

**Entity Factory - Forbidden:**
- Changing existing entity type definitions
- Modifying core validation logic
- Breaking backward compatibility
- Renaming required properties

**OCEAN System - Allowed:**
- Adding new inference methods (with approval)
- Improving behavioral → trait mappings (with approval)
- Adding documentation and examples

**OCEAN System - Forbidden:**
- Changing trait scales (must remain 0-1)
- Adding new traits (OCEAN is standardized: O/C/E/A/N only)
- Renaming traits
- Modifying trait interpretation logic

**Neo4j Adapter - Allowed:**
- Adding new query methods
- Performance optimizations (with approval)
- Adding indexes (with migration plan)

**Neo4j Adapter - Forbidden:**
- Changing schema without migration
- Deleting node types
- Renaming node properties
- Modifying relationship types

### 7.3 Integration with Protected Modules

If a subsystem needs to integrate with Entity Factory, OCEAN, or Neo4j:

**Use adapter modules, NOT direct modification:**

```python
# ✅ CORRECT: Adapter pattern
class SmartIngestorEntityAdapter:
    """Adapts Smart Ingestor output to EntityFactory format."""
    def to_entity_format(self, extracted_data: dict) -> dict:
        # Transform without modifying EntityFactory
        pass

# ❌ WRONG: Modifying core infrastructure
# Don't edit entity_factory/factory.py to add Smart Ingestor logic
```

---

## 8. Handoff Dossiers

### 8.1 When to Generate

For large tasks or subsystems, generate a **Handoff Dossier** when:
- Completing a subsystem implementation phase
- Ending a work session with incomplete work
- Transferring work to another AI instance or human
- Reaching context limit
- Explicitly requested

### 8.2 Dossier Template

Use the template stored in:
- `docs/UNIVERSAL_IMPLEMENTATION_PROMPT.md`, or
- Subsystem-specific template if provided

**Required Sections:**
```markdown
# SUBSYSTEM HANDOFF DOSSIER — [Name]

## 1. SYSTEM OVERVIEW
[Brief description of subsystem purpose and architecture]

## 2. COMPLETED MODULES
[List each finished module with:
 - Module name and file path
 - Public API summary
 - Key behaviors
 - Dependencies
 - Integration status]

## 3. PENDING MODULES
[List remaining modules in implementation order:
 - Module name
 - Purpose
 - Dependencies
 - Estimated complexity]

## 4. PUBLIC INTERFACES (SOURCE OF TRUTH)
[Exact function signatures, classes, and data structures]

## 5. INTEGRATION POINTS
[How this subsystem connects to rest of LMS/MANTLE:
 - What it imports
 - What imports it
 - API endpoints
 - Database schema dependencies]

## 6. TESTING STATUS
[What's tested, what needs tests, test coverage]

## 7. KNOWN ISSUES / BLOCKERS
[Any problems preventing progress]

## 8. DO-NOTS (HARD CONSTRAINTS)
[Explicit rules preventing drift for this subsystem]

## 9. NEXT STEPS
[Explicit next action for continuation]
```

### 8.3 Dossier Maintenance

**After completing each module:**
- Update "COMPLETED MODULES" section
- Remove from "PENDING MODULES" section
- Update "TESTING STATUS"
- Add any new "KNOWN ISSUES"

**Never:**
- Leave dossier out of date
- Omit critical information
- Generate incomplete dossiers

---

## 9. When Context Is Constrained

### 9.1 Context Exhaustion Protocol

If you lose context, reach token limits, or are unsure:

**DO NOT:**
- Guess about architecture
- Assume previous decisions
- Proceed with incomplete information
- Invent structure to fill gaps

**DO:**
1. **STOP immediately**
2. **State:** "Context is constrained, I need to reload information"
3. **Request:**
   - Re-open relevant design doc or contract
   - Regenerate Handoff Dossier
   - Review subsystem contract
4. **Wait** for information before proceeding

### 9.2 Safe Assumptions

If you **cannot** see design documents, assume:
- You are **NOT allowed** to alter architecture
- Existing structure is **correct**
- Changes must be **minimal**
- You should **ask** before making decisions

**Default to conservative behavior.**

---

## 10. Code Quality Standards

### 10.1 Type Hints (REQUIRED)

All functions must have complete type hints.

```python
# ✅ CORRECT
def extract_entities(
    text: str, 
    config: ExtractionConfig
) -> list[Entity]:
    pass

async def collapse_entity(
    entity_id: str, 
    observer_id: str
) -> EntityState | None:
    pass

# ❌ WRONG
def extract_entities(text, config):  # Missing type hints
    pass
```

**Requirements:**
- Parameter types for all arguments
- Return type (including `None` if applicable)
- Use `Optional[T]` or `T | None` for nullable types
- Use `list[T]`, `dict[K, V]` for collections (Python 3.10+)

### 10.2 Docstrings (REQUIRED)

All **public functions and classes** must have docstrings.

```python
# ✅ CORRECT
def collapse_entity(entity_id: str, observer_id: str) -> EntityState:
    """
    Collapse entity from superposition to eigenstate.
    
    Triggers the Decoherence Engine to resolve entity state based on
    elapsed time since last observation and current observer context.
    
    Args:
        entity_id: Unique identifier for the entity to collapse
        observer_id: ID of the character/player observing the entity
        
    Returns:
        EntityState with canonical properties after collapse
        
    Raises:
        EntityNotFoundError: If entity_id doesn't exist in database
        CollapseFailedError: If collapse computation fails
        ObserverNotFoundError: If observer_id is invalid
        
    Example:
        >>> state = collapse_entity("npc_guard_123", "player_jim")
        >>> print(state.properties["mood"])
        "vigilant"
    """
    pass

# ❌ WRONG
def collapse_entity(entity_id: str, observer_id: str) -> EntityState:
    pass  # No docstring
```

**Private functions** (prefixed with `_`) may have shorter docstrings or none if purpose is obvious from name and context.

### 10.3 Error Handling (REQUIRED)

All **external calls** must have error handling:
- LLM API calls
- Database operations
- File I/O
- Network requests

```python
# ✅ CORRECT
async def call_gemini(prompt: str) -> str:
    """Call Gemini API with error handling."""
    try:
        response = await self.client.generate_content(prompt)
        return response.text
    except APIError as e:
        logger.error(f"Gemini API failed: {e}")
        raise IngestionError(f"AI extraction failed: {e}") from e
    except TimeoutError as e:
        logger.error(f"Gemini API timeout: {e}")
        raise IngestionError("AI extraction timed out") from e
    except Exception as e:
        logger.error(f"Unexpected error during Gemini call: {e}")
        raise

# ❌ WRONG
async def call_gemini(prompt: str) -> str:
    response = await self.client.generate_content(prompt)
    return response.text  # No error handling
```

### 10.4 Logging (REQUIRED)

All **orchestrators** and **critical functions** must log:
- Entry/exit for orchestrator methods
- Errors and exceptions
- Key state changes
- Performance metrics (if relevant)

```python
# ✅ CORRECT
import logging
logger = logging.getLogger(__name__)

async def ingest(self, file_path: str) -> IngestionResult:
    """Ingest document with comprehensive logging."""
    logger.info(f"Starting ingestion: {file_path}")
    
    try:
        result = await self._process(file_path)
        logger.info(
            f"Ingestion complete: {file_path} "
            f"({result.entity_count} entities extracted)"
        )
        return result
        
    except IngestionError as e:
        logger.error(f"Ingestion failed for {file_path}: {e}")
        raise
        
    except Exception as e:
        logger.critical(f"Unexpected error during ingestion: {e}")
        raise

# ❌ WRONG
async def ingest(self, file_path: str) -> IngestionResult:
    result = await self._process(file_path)
    return result  # No logging
```

**Logging Levels:**
- `DEBUG`: Detailed information for debugging
- `INFO`: General information about normal operation
- `WARNING`: Something unexpected but recoverable
- `ERROR`: Error occurred, operation failed
- `CRITICAL`: Severe error, system may be unstable

---

## 11. Subsystem-Specific Rules

### 11.1 Smart Ingestor

**Pipeline Order (IMMUTABLE):**

The Smart Ingestor uses a multi-pass pipeline. Passes must execute in this exact order:

1. **Format Detection** - Identify document type
2. **Scene Segmentation** (if narrative) - Break into logical sections
3. **Entity Extraction** - Extract characters, locations, factions, etc.
4. **Relationship Extraction** - Map connections between entities
5. **Enrichment** - Infer OCEAN personalities, motivations, fears
6. **Confidence Scoring** - Calculate certainty of inferences
7. **Canon Status Assignment** - Mark locked/TBD/placeholder/inferred
8. **Neo4j Mapping** - Transform to graph nodes and relationships

**You may NOT:**
- Skip pipeline passes
- Reorder passes without contract update and approval
- Add new passes without contract update
- Merge passes without approval

**Context Keys Per Pass:**

Each pass has defined input/output keys (see `src/smart_ingestor/SUBSYSTEM_CONTRACT.md`).

**Example:**
```python
# Pass 1 writes:
context["document_format"] = "faction_dossier"

# Pass 3 reads Pass 1, writes:
doc_format = context["document_format"]
context["raw_entities"] = [Entity(...), ...]

# Pass 5 reads Pass 3, writes:
entities = context["raw_entities"]
context["enriched_entities"] = [EnrichedEntity(...), ...]
```

### 11.2 Decoherence Engine

**Determinism Requirement (CRITICAL):**

All state collapses must be **deterministic**.

**RULE:** Same inputs must ALWAYS produce same output.

**Requirements:**
```python
# Same entity + same observer + same time + same seed = same eigenstate
collapse(entity_id="guard_123", observer="player_1", time=T, seed=42)
# Must ALWAYS return identical EntityState

# ✅ CORRECT: Deterministic collapse
def collapse_with_seed(entity, dt, context, seed):
    random.seed(seed)  # Seeded randomness
    # ... deterministic computation
    return eigenstate

# ❌ WRONG: Non-deterministic collapse
def collapse_non_deterministic(entity, dt, context):
    random_value = random.random()  # No seed!
    current_time = datetime.now()   # Uses real time!
    # ... non-deterministic computation
```

**All Evolution Operators must be pure functions:**
- No API calls
- No database writes (only reads)
- No randomness without seed
- No `datetime.now()` (use game_time from context)

**Reproducibility is CRITICAL for:**
- Debugging collapsed states
- Time travel reconstruction
- Consistency across sessions
- Validating simulation behavior

### 11.3 Entity Factory (PROTECTED)

**Modification Rules:**

Entity Factory is **core infrastructure**. Changes require explicit approval.

**Protected Files:**
```
src/entity_factory/
├── factory.py           [IMMUTABLE without approval]
├── templates.py         [IMMUTABLE without approval]
└── validators.py        [IMMUTABLE without approval]
```

**Allowed with Approval:**
- Adding new entity types (must follow template pattern)
- Extending existing templates (must maintain backward compatibility)
- Adding validation rules (must not break existing entities)

**Forbidden:**
- Changing existing entity type definitions
- Modifying required property lists for existing types
- Breaking backward compatibility
- Renaming core properties (name, id, type, etc.)

**Process for Approved Changes:**
1. Propose change with justification
2. Show impact analysis (what breaks, what needs updating)
3. Wait for explicit approval
4. Implement with migration plan if needed
5. Update all dependent subsystems
6. Add tests for new functionality

### 11.4 OCEAN Personality System (PROTECTED)

**Trait Definitions (IMMUTABLE):**

The OCEAN model uses the Big Five personality framework. These trait definitions are **standardized** and cannot be changed.

**Traits:**
- **O**penness: Creativity, curiosity, openness to experience (0-1)
- **C**onscientiousness: Discipline, reliability, organization (0-1)
- **E**xtraversion: Sociability, assertiveness, energy (0-1)
- **A**greeableness: Compassion, cooperation, trust (0-1)
- **N**euroticism: Emotional instability, anxiety, moodiness (0-1)

**You may NOT:**
- Change trait names (O/C/E/A/N are standard)
- Change trait scales (must remain 0-1 normalized)
- Add new traits (Big Five is complete model)
- Remove traits
- Modify trait interpretation formulas without approval

**Allowed with Approval:**
- New inference methods (behavior → OCEAN mapping)
- Better calibration of trait scores
- Additional helper functions for trait manipulation
- Visualization/reporting improvements

### 11.5 Neo4j Adapter (PROTECTED)

**Schema Change Protocol (STRICT):**

Database schema changes are **high-risk operations** requiring careful planning.

**Process for Schema Changes:**
1. **Propose:** Document proposed change with justification
2. **Impact Analysis:** What existing data is affected?
3. **Migration Plan:** How will existing nodes/relationships update?
4. **Rollback Plan:** How to undo if migration fails?
5. **Approval:** Wait for explicit human approval
6. **Test Migration:** Run on copy of production data
7. **Implement:** Execute migration with logging and validation
8. **Verify:** Confirm data integrity after migration

**Schema Changes Requiring Approval:**
- Adding new node types
- Adding new relationship types
- Adding properties to existing node types
- Renaming properties
- Deleting properties (requires migration)
- Changing property types
- Adding constraints or indexes

**Low-Risk Changes (Still Announce):**
- Adding optional properties (no migration needed)
- Adding indexes for performance
- Adding new query methods

**NEVER:**
- Delete node types without migration
- Change relationship directions
- Remove properties without migration
- Modify schema in production without testing

---

## 12. Enforcement & Consequences

### 12.1 Violation Severity

**Minor Violation:**
- Adding import without checking dependency direction
- Skipping docstring on internal function
- Minor deviation from code style
- Missing type hint on obvious parameter

**Action:** Warning issued → Correction required before proceeding

**Major Violation:**
- Generating entire subsystem without module-by-module approval
- Modifying protected infrastructure without approval
- Creating circular dependencies
- Violating pipeline order
- Breaking determinism in Decoherence Engine

**Action:** Rollback to last valid state → Restart from approved checkpoint

**Repeated Violations:**
- Consistently ignoring first-response rule
- Pattern of skipping handoff dossier updates
- Multiple dependency direction violations
- Frequent unauthorized refactoring

**Action:** Full context reset → Review all completed work → Regenerate handoff dossier

### 12.2 Enforcement Examples

**Example 1: Minor Violation**
```
AI: [Adds import without checking dependency direction]
HUMAN: "That import violates dependency direction. Entity Factory cannot import from Smart Ingestor."
AI: "You're correct. I'll remove the import and use an adapter pattern instead."
[Correction made, work continues]
```

**Example 2: Major Violation**
```
AI: [Generates all 8 Smart Ingestor modules in one response]
HUMAN: "This violates module-by-module rule. Rollback."
AI: [Deletes all generated code]
AI: [Performs repo scan]
AI: "WAITING FOR APPROVAL TO BEGIN MODULE 1. NO CODE GENERATED."
[Restart from approved process]
```

**Example 3: Repeated Violations**
```
AI: [Third time skipping handoff dossier update]
HUMAN: "Repeated violation of handoff dossier rule. Full reset."
AI: [Generates complete handoff dossier for all work]
AI: [Reviews all completed modules]
AI: "Dossier complete. All work reviewed. Ready to proceed correctly."
```

### 12.3 Self-Correction

If you realize you've violated a rule:
1. **STOP immediately**
2. **Acknowledge:** "I violated [rule X] by [action Y]"
3. **Propose correction:** "I will fix this by [solution Z]"
4. **Wait for approval** before proceeding

**DO NOT:**
- Continue as if nothing happened
- Hope human doesn't notice
- Argue that violation was justified
- Make excuses

---

## 13. Override Protocol

### 13.1 When Rules Can Be Overridden

These rules can be overridden **ONLY** by:

1. **Explicit human command:**
   - "Override rule [X], proceed with [Y]"
   - Must be clear and unambiguous
   - Must specify which rule is being overridden

2. **Documented in commit message:**
   - Commit must include: `RULE OVERRIDE: [reason]`
   - Explanation of why override was necessary
   - What rule was overridden

3. **Updated in this file afterward:**
   - If override becomes permanent policy, update rules
   - If temporary, document as exception

### 13.2 Self-Override is FORBIDDEN

**You may NOT:**
- Decide a rule doesn't apply in this case
- Interpret rules loosely to allow what you want
- Override rules without explicit human permission
- Claim "this is a special situation"

**If you believe a rule should be overridden:**
1. **STOP**
2. **Explain** why you think override is needed
3. **Request** explicit override permission
4. **Wait** for human decision

### 13.3 Override Example

```
AI: "I need to modify Entity Factory to add Smart Ingestor integration. This violates rule 7.1 (Entity Factory protection). Should I proceed?"

HUMAN: "Override rule 7.1, proceed with adding adapter hooks only. Do not modify core factory logic."

AI: "Acknowledged. Overriding rule 7.1 with constraint: adapter hooks only. Proceeding."

[Later in commit message]
"RULE OVERRIDE: Modified Entity Factory (rule 7.1) to add adapter hooks for Smart Ingestor integration. Core factory logic unchanged."
```

---

## 14. Document Authority Hierarchy

### 14.1 Authority Ranking

When multiple documents provide conflicting guidance, follow this hierarchy (highest → lowest):

1. **`.cursor/rules.md`** (this file) — Constitutional law
2. **`docs/ARCHITECTURE_V2.md`** — System blueprint and long-term vision
3. **`docs/UNIVERSAL_IMPLEMENTATION_PROMPT.md`** — Subsystem build template
4. **`src/<subsystem>/SUBSYSTEM_CONTRACT.md`** — Individual subsystem contracts
5. **Individual commit messages** — Specific decisions for specific changes

**Rule:** Higher authority **always** overrides lower authority.

### 14.2 Conflict Resolution

**If documents conflict:**

1. **Check authority level** - Higher document wins
2. **If same level** - Assume most recent is correct, but ASK HUMAN
3. **If unclear** - DO NOT GUESS, ASK HUMAN

**Example:**
```
ARCHITECTURE_V2.md says: "Smart Ingestor has 7 passes"
SUBSYSTEM_CONTRACT.md says: "Smart Ingestor has 8 passes"

Resolution: SUBSYSTEM_CONTRACT.md is more specific (level 4 authority)
Action: Follow 8-pass structure, flag discrepancy to human
```

### 14.3 Consulting Authority

**Before starting major work:**
1. Read `.cursor/rules.md` (this file) for global rules
2. Read `ARCHITECTURE_V2.md` for system context
3. Read subsystem-specific contract for detailed requirements
4. Ask human if any conflicts or ambiguities exist

**During work:**
- If unsure, consult higher-authority document
- If still unclear, **ASK HUMAN**
- Never proceed with ambiguous guidance

---

## 15. Success Criteria

### 15.1 You Are Following These Rules Correctly When:

**Architectural Discipline:**
- ✅ Every module has clear boundaries
- ✅ Every import respects dependency direction
- ✅ Zero circular dependencies
- ✅ Zero architectural drift

**Implementation Discipline:**
- ✅ First response always contains repo scan (no code)
- ✅ Modules implemented one at a time
- ✅ Every change is minimal diff
- ✅ Every response includes only approved work

**Quality Standards:**
- ✅ All functions have type hints and docstrings
- ✅ All external calls have error handling
- ✅ All orchestrators have comprehensive logging
- ✅ Code is clear, maintainable, and well-documented

**Governance:**
- ✅ Handoff dossiers always up to date
- ✅ Subsystem contracts followed exactly
- ✅ Protected infrastructure unchanged without approval
- ✅ No forbidden actions without explicit override

**Communication:**
- ✅ Uncertainties stated clearly
- ✅ Assumptions validated before proceeding
- ✅ Violations acknowledged and corrected
- ✅ Questions asked when guidance unclear

### 15.2 Red Flags (Self-Check)

If you find yourself doing any of these, **STOP**:
- ❌ "I'll just quickly refactor this..."
- ❌ "This import should be fine..."
- ❌ "I'll improve this code while I'm here..."
- ❌ "The rule probably doesn't apply in this case..."
- ❌ "I'll generate all the modules at once to save time..."
- ❌ "I don't need to update the handoff dossier yet..."
- ❌ "I'll add this feature even though it wasn't requested..."

**These are all violations.** Stop and follow proper protocol.

---

## 16. Final Rule: When In Doubt

**ALWAYS:**
- Preserve structure
- Preserve contracts
- Preserve intent
- Make the smallest, safest change that solves the current task

**ASK HUMAN if you are uncertain about:**
- Whether a change violates these rules
- Whether an import respects dependency direction
- Whether a modification is in scope
- Whether a refactor is safe
- Whether architecture needs to change
- Whether you should proceed

**NEVER:**
- Guess and hope you're right
- Assume you know what human wants
- Proceed anyway "just to try"
- Experiment without approval

---

**When uncertain: STOP. EXPLAIN. ASK. WAIT.**

This is not a sign of failure. This is correct behavior.

---

**END OF CURSOR PROJECT RULES**

*Version 2.0 (Integrated) — Last Updated: 2025-12-01*
```

