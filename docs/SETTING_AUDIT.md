# Setting Specific Reference Audit

**Date:** 2025-11-29
**Status:** Audit Complete

## Findings

The following files contain hardcoded references to the "Aethermoor" setting or specific world details that should be parameterized or removed to ensure the system is setting-agnostic.

### 1. Source Code

**File:** `src/prompts/dm_prompts.py`
- **Line 20:** `SYSTEM_V2_4 = """You are the AI Dungeon Master for the Aethermoor campaign.` -> Replace with `{campaign_name}`
- **Line 30:** `World: High-magic dark fairy tale (beautiful but wrong)` -> Replace with `{world_tone}`
- **Line 37:** `Setting: Aethermoor - reality is unstable, magic corrupts` -> Replace with `{setting_description}`
- **Line 38:** `Year: 1247, Third Age` -> Replace with `{current_date}`
- **Line 40:** `Naming: Celtic/Gaelic inspired (Thornhaven, Mor'vale, Kaelith)` -> Replace with `{naming_conventions}`
- **Line 80:** `ENTITY_GENERATION_TEMPLATE = """You are creating a new {entity_type} for the Aethermoor campaign.` -> Replace with `{campaign_name}`

**File:** `src/prompts/auditor_prompts.py`
- **Line 16:** `SYSTEM = """You are the Lore Auditor for the Aethermoor campaign.` -> Replace with `{campaign_name}`

### 2. Tests

**File:** `tests/test_prompts.py`
- **Line 46, 53:** References to "Celtic" in test data. (Acceptable for testing, but noted).

### 3. Documentation

**File:** `docs/mantle/WORLDBUILDING_RULES.md`
- Contains detailed setting rules for Aethermoor. This file serves as the "Campaign Seed" input and is expected to be specific.

## Recommendations

1.  **Parameterize Prompts:** Update `DMPrompts` and `AuditorPrompts` to accept `campaign_context` dictionary containing `name`, `tone`, `date`, `naming_conventions`, etc.
2.  **Inject Context:** Update `DMAgent` and `AuditorAgent` to load these values from environment variables or a configuration file (`campaign.json`) and pass them when building prompts.
3.  **Default Values:** Provide generic defaults if configuration is missing (e.g., "Fantasy Setting", "Medieval", etc.).

## Action Plan

1.  Update `src/prompts/dm_prompts.py` with placeholders.
2.  Update `src/prompts/auditor_prompts.py` with placeholders.
3.  Update `DMAgent` to populate these placeholders from `WORLDBUILDING_RULES.md` or a new config source.

