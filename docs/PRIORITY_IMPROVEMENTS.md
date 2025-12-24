# Priority Improvements for Storyweaver

**Last Updated:** December 24, 2025

This document outlines the top improvements needed to ensure user engagement, align with the vision of a "personal mythology engine," and achieve reliable deployment.

---

## Vision Reminder

Storyweaver aims to be a **personal mythology engine** that serves diverse storytellers:
- TTRPG veterans seeking a solo experience
- Romance readers wanting interactive stories
- Mystery lovers who want to solve puzzles
- Anyone who dreams of living inside their favorite genres

The core promise: **Your story, your rules, your world.**

---

## Tier 1: Critical (Blocking MVP Launch)

### 1. Fix Gemini API Timeout Issue
**Impact:** App is unusable without this
**Effort:** Medium (1-2 days)

The gameplay loop times out because Gemini calls hang. Fixes:

```python
# Option A: Pre-warm on startup
@asynccontextmanager
async def lifespan(app):
    model = get_gemini_model()
    # Warm up the connection
    await asyncio.to_thread(model.generate_content, "Hello",
        generation_config={"max_output_tokens": 5})
    yield

# Option B: Switch to faster model
model = genai.GenerativeModel("gemini-1.5-flash")  # vs gemini-2.0-flash-exp

# Option C: Add streaming for perceived responsiveness
for chunk in model.generate_content(prompt, stream=True):
    yield chunk.text
```

### 2. Session Persistence
**Impact:** Users lose all progress on app restart/redeploy
**Effort:** Medium (1-2 days)

Sessions are stored in-memory (`_active_sessions = {}`). On every deploy, all sessions vanish.

Solution:
```python
# Use SQLite for session storage (already have experiential_memory.db)
# Or Redis for multi-instance support

class SessionStore:
    async def save(self, session_id: str, data: dict): ...
    async def load(self, session_id: str) -> dict: ...
    async def list_active(self) -> List[str]: ...
```

### 3. Frontend Error Handling
**Impact:** Users see infinite spinner on failures
**Effort:** Low (0.5 days)

Add timeout and error handling to frontend:
```javascript
// After 30 seconds, show error with retry
setTimeout(() => {
    if (stillLoading) {
        showError("The story is taking longer than expected. Would you like to try again?");
        showRetryButton();
    }
}, 30000);
```

---

## Tier 2: High Priority (User Engagement)

### 4. Lore Base Selection in UI
**Impact:** Users can't access pre-made worlds
**Effort:** Low (0.5 days)

The API supports lore bases, but the UI doesn't use them. Add:
- Dropdown in session creation: "Choose a World"
- Options: Fresh Canvas, The Gilded Court, The Iron Coast, + Custom
- Show entity count and description for each

### 5. Connect Ingested Lore to Gameplay
**Impact:** Lore is ignored during storytelling
**Effort:** Medium (1 day)

Currently, `_handle_active_play` queries Neo4j but doesn't effectively use lore entities. Enhance:

```python
# Query NPCs with OCEAN profiles for the current scene
npcs = await db.execute("""
    MATCH (c:Character)
    WHERE c.source STARTS WITH 'lore_base:'
    RETURN c.name, c.description, c.openness, c.agreeableness, c.extraversion
    LIMIT 3
""")

# Include in prompt
prompt += f"\nAvailable NPCs (use their personalities):\n"
for npc in npcs:
    prompt += f"- {npc['name']}: {describe_ocean(npc)}\n"
```

### 6. "Continue Your Story" Feature
**Impact:** Users can return to their adventures
**Effort:** Medium (1 day)

With session persistence (#2), add:
- "Your Stories" page listing saved sessions
- Resume from last action
- Session metadata (world, character, last played)

### 7. Suggested Actions UI
**Impact:** Helps new users know what to do
**Effort:** Low (0.5 days)

The API returns `suggested_actions` in DMResponse but frontend ignores it:
```json
{
    "narrative": "The captain eyes you suspiciously...",
    "suggested_actions": [
        "Introduce yourself",
        "Ask about joining the crew",
        "Offer a bribe"
    ]
}
```

Display as clickable buttons below the narrative.

---

## Tier 3: Vision Alignment (Personal Mythology Engine)

### 8. Character Sheet / Journal
**Impact:** Makes the experience feel personal
**Effort:** Medium (2 days)

Track and display:
- Character name, concept, traits
- Key relationships formed
- Important events experienced
- Items/knowledge acquired

```python
class CharacterJournal:
    name: str
    concept: str
    relationships: List[Relationship]  # "Allied with Captain Blacktide"
    memories: List[Memory]  # Key story moments
    inventory: List[str]
```

### 9. NPC Memory & Consistency
**Impact:** NPCs feel alive and remember the player
**Effort:** High (3-5 days)

Use experiential memory to track:
- What each NPC knows about the player
- Past interactions and their outcomes
- Relationship status (friend, enemy, neutral)

```python
# When player meets NPC again
npc_memory = await experiential_memory.get_npc_context(npc_id, player_id)
prompt += f"\n{npc.name} remembers: {npc_memory.summary}"
```

### 10. Genre-Specific Mechanics
**Impact:** Romance feels different from combat fantasy
**Effort:** High (1-2 weeks)

Each genre should have unique mechanics:

| Genre | Mechanic |
|-------|----------|
| Romance | Relationship meters, emotional beats |
| Mystery | Clue collection, suspect tracking |
| Horror | Sanity/tension meter, limited information |
| Adventure | Discovery tracking, exploration rewards |
| Fantasy | Magic system, quest log |

### 11. OCEAN-Driven NPC Behavior
**Impact:** NPCs feel psychologically real
**Effort:** Medium (2 days)

Use stored OCEAN profiles to influence:
- Dialogue tone (high agreeableness = warmer responses)
- Reaction to player actions (high neuroticism = more reactive)
- Decision-making (high conscientiousness = more predictable)

```python
def get_npc_reaction_modifier(npc: Character, action: str) -> str:
    if "aggressive" in action and npc.agreeableness < 0.3:
        return "responds in kind, matching your aggression"
    elif "kind" in action and npc.agreeableness > 0.7:
        return "warms to you immediately"
    # etc.
```

---

## Tier 4: Reliability & Scale

### 12. Health Check Tolerance
**Impact:** App marked unhealthy during AI calls
**Effort:** Low (0.5 days)

Fly.io health checks fail when Gemini is slow. Fix:
```toml
# fly.toml
[[services.http_checks]]
  interval = 60000  # 60 seconds (was 15)
  timeout = 10000
  grace_period = "30s"
```

### 13. Circuit Breaker Tuning
**Impact:** Graceful degradation on AI failures
**Effort:** Low (0.5 days)

Current circuit breaker may be too aggressive. Tune:
```python
CircuitBreaker(
    failure_threshold=5,  # Allow more failures
    recovery_timeout=30,  # Recover faster
    half_open_max_calls=2
)
```

### 14. Rate Limiting by IP
**Impact:** Prevent abuse, control costs
**Effort:** Low (0.5 days)

Add per-IP rate limiting in addition to session-based:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.post("/session/{id}/action")
@limiter.limit("10/minute")
async def process_action(...):
```

### 15. Monitoring & Alerting
**Impact:** Know when things break
**Effort:** Medium (1 day)

Add:
- Sentry for error tracking
- Prometheus metrics for AI latency
- Alerts when circuit breaker opens

---

## Tier 5: Future Expansion

### 16. Multiplayer / Shared Worlds
**Impact:** Social storytelling
**Effort:** Very High

Allow multiple players in same world with:
- Shared lore base
- Individual character sheets
- Cross-references in narratives

### 17. Voice Integration
**Impact:** Accessibility, immersion
**Effort:** High

- Text-to-speech for narration
- Speech-to-text for actions
- Different voices for different NPCs

### 18. Mobile App
**Impact:** Accessibility
**Effort:** Very High

Native iOS/Android apps for:
- Offline session caching
- Push notifications for story updates
- Better mobile UX

### 19. Community Lore Sharing
**Impact:** User-generated content
**Effort:** High

Allow users to:
- Publish their lore bases
- Rate and discover others' worlds
- Fork and customize existing lore

### 20. Rule System Framework
**Impact:** Customizable game mechanics
**Effort:** High

```python
class RuleEngine(Protocol):
    def check_action(self, action: str, context: GameContext) -> ActionResult
    def resolve_conflict(self, participants: List[Character]) -> Resolution
    def apply_consequence(self, result: ActionResult) -> List[WorldChange]
```

Built-in rule sets:
- Narrative Only (current)
- Lite Rules (simple checks)
- Full TTRPG (dice, stats, combat)

---

## Implementation Roadmap

### Week 1: Fix Critical Blockers
- [ ] Fix Gemini timeout (#1)
- [ ] Add session persistence (#2)
- [ ] Frontend error handling (#3)
- [ ] Health check tuning (#12)

### Week 2: Core Engagement
- [ ] Lore base UI selection (#4)
- [ ] Connect lore to gameplay (#5)
- [ ] Suggested actions UI (#7)
- [ ] Continue story feature (#6)

### Week 3: Personal Mythology
- [ ] Character journal (#8)
- [ ] OCEAN-driven NPC behavior (#11)
- [ ] Basic genre mechanics (#10)

### Week 4: Polish & Scale
- [ ] NPC memory (#9)
- [ ] Rate limiting (#14)
- [ ] Monitoring (#15)

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Session completion rate | 0% (blocked) | >50% |
| Average session length | N/A | >10 turns |
| Return user rate | N/A | >30% |
| AI response time (p95) | Timeout | <10s |
| Deploy success rate | ~80% | >99% |

---

*This document should be reviewed and updated after each development sprint.*
