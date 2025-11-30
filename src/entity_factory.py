"""
Entity Factory - Template-based entity generation with quality control.

SETTING-AGNOSTIC: Templates provide structure and quality guidelines
but do NOT specify campaign setting, world names, naming conventions,
or tone. All setting-specific context comes from campaign seed lore
and existing entities.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

class EntityType(str, Enum):
    """Valid entity types in the lore system."""
    CHARACTER = "Character"
    LOCATION = "Location"
    FACTION = "Faction"
    ITEM = "Item"
    EVENT = "Event"
    CONCEPT = "Concept"

@dataclass
class EntityTemplate:
    """Template defining structure and guidelines for an entity type."""
    entity_type: EntityType
    required_properties: List[str]
    optional_properties: List[str]
    generation_guidelines: str
    naming_conventions: str

class EntityFactory:
    """
    Factory for creating lore-consistent entities with AI guidance.
    
    SETTING-AGNOSTIC: Works with any campaign setting (fantasy, sci-fi, etc.)
    by pulling context from campaign seed lore and existing entities.
    """
    
    TEMPLATES = {
        EntityType.CHARACTER: EntityTemplate(
            entity_type=EntityType.CHARACTER,
            required_properties=["name", "description", "role"],
            optional_properties=[
                "species", "age", "alignment", "occupation", "faction",
                "personality_traits", "goals", "fears", "secrets",
                "relationships", "background"
            ],
            generation_guidelines="""CHARACTER GENERATION GUIDELINES:

**Universal Character Depth:**
- Every NPC needs clear motivation: a GOAL (what they want) and a FEAR (what they're avoiding)
- Include at least ONE secret or hidden agenda (not immediately apparent to players)
- Align personality with role, but add contradictions for depth

**Personality:**
- 2-3 distinctive personality traits (not generic)
- One memorable quirk or mannerism (speech pattern, habit, distinctive item)
- Morally complex - avoid purely good/evil characters

**Setting Integration:**
- Use naming conventions consistent with the campaign setting
- Reference existing factions when possible (creates web of connections)
- Consider their relationship to the world's unique mechanics (magic, technology, etc.)
- Connect to established lore from existing entities

**Tone Consistency:**
- Match the tone established in campaign seed lore
- Maintain aesthetic consistency with existing NPCs
- NPCs should feel authentic to the setting

**Quality Standards:**
- Avoid stereotypes and clichés
- Make NPCs memorable with unique details
- Everyone has layers - surface presentation vs hidden truth

**Example Structure:**
[Name] - [Brief Role Description]
- Role: [Occupation/Function]
- Goal: [What they want to achieve]
- Fear: [What they're trying to avoid]
- Secret: [Hidden information]
- Personality: [Surface traits] (surface), [Hidden traits] (hidden)
- Quirk: [Memorable detail]""",
            naming_conventions="Use naming conventions consistent with campaign setting and existing entities"
        ),
        
        EntityType.LOCATION: EntityTemplate(
            entity_type=EntityType.LOCATION,
            required_properties=["name", "description", "type"],
            optional_properties=[
                "geography", "climate", "population", "government",
                "notable_features", "dangers", "resources",
                "connected_to", "history", "atmosphere"
            ],
            generation_guidelines="""LOCATION GENERATION GUIDELINES:

**Connectivity:**
- Reference nearby locations when possible (roads to, borders with, visible from)
- Create a sense of place in the larger world (not isolated)
- Include travel time/difficulty to known locations if relevant

**Environmental Details:**
- Include hazards or challenges appropriate to location type
- Consider unique world mechanics (how do they manifest here?)
- Natural dangers appropriate to setting and location type

**Atmosphere:**
- Create distinctive atmosphere (what makes this place memorable?)
- Sensory details (sights, sounds, smells)
- Mood and tone consistent with campaign setting

**Power & Politics:**
- Who controls this location? (faction, ruler, anarchic, contested)
- What resources or strategic value does it have?
- Recent events that shaped it

**Adventure Hooks:**
- Include 1-2 rumors or mysteries about the location
- Unresolved tensions (conflicts, mysteries, unexplained phenomena)
- Something players could investigate or get drawn into

**Naming:**
- Follow naming conventions from campaign setting
- Reference existing location naming patterns
- Ensure consistency with world's language/culture

**Quality Standards:**
- Avoid generic fantasy/sci-fi tropes unless they fit the setting
- Make locations feel lived-in and authentic
- Include specific, concrete details""",
            naming_conventions="Follow naming patterns from campaign setting and existing locations"
        ),
        
        EntityType.FACTION: EntityTemplate(
            entity_type=EntityType.FACTION,
            required_properties=["name", "description", "motivation"],
            optional_properties=[
                "leader", "base_of_operations", "membership_size",
                "methods", "enemies", "allies", "resources",
                "secrets", "goals", "public_face", "hidden_agenda"
            ],
            generation_guidelines="""FACTION GENERATION GUIDELINES:

**Ideology & Motivation:**
- Clear driving motivation (power, knowledge, survival, redemption, revenge, ideology)
- Specific goal they're actively working toward (not vague)
- Justification for their methods (they believe they're right)

**Moral Complexity:**
- No purely evil factions - everyone is the hero of their own story
- Sympathetic motivation potentially twisted by extreme methods
- Internal conflicts (not all members agree on tactics)

**Relationships:**
- Reference existing factions as allies or enemies when possible
- Complex relationships (ally on one issue, enemy on another)
- Historical context (why do they oppose/support each other?)

**Public vs Hidden:**
- What they claim to be vs what they actually are
- Public activities vs secret operations
- Who knows their true nature?

**Methods & Resources:**
- How do they pursue their goals? (infiltration, force, persuasion, technology, magic)
- What resources do they control? (wealth, knowledge, power, people)
- What lines will they cross? (and which won't they?)

**Naming:**
- Follow faction naming patterns from campaign setting
- Consider organizational structure (guild, clan, corporation, order, etc.)
- Name should reflect purpose or ideology

**Quality Standards:**
- Avoid one-dimensional "evil empire" or "good rebels" tropes
- Make factions feel like real organizations with complex motivations
- Internal politics and power struggles""",
            naming_conventions="Follow faction naming patterns from campaign setting"
        ),
        
        EntityType.ITEM: EntityTemplate(
            entity_type=EntityType.ITEM,
            required_properties=["name", "description", "type"],
            optional_properties=[
                "power", "drawback", "origin", "creator",
                "current_owner", "material", "rarity",
                "requirements", "history"
            ],
            generation_guidelines="""ITEM GENERATION GUIDELINES:

**Power Balance:**
- Powerful items should have drawbacks, costs, or limitations
- Power level should match item rarity/importance
- Consider attunement requirements or usage costs

**History & Origin:**
- Who created it and why? (if legendary/unique)
- What events is it connected to?
- Previous owners and their fates

**Setting Integration:**
- Consistent with world's power system (magic, technology, etc.)
- Reflects crafting traditions of the setting
- Connected to existing lore when possible

**Naming:**
- Follow item naming conventions from campaign setting
- Descriptive or evocative names for unique items
- Generic names for common items

**Quality Standards:**
- Avoid generic "+1 sword" unless appropriate to setting
- Make unique items memorable with specific details
- Clear mechanical effects if relevant to gameplay""",
            naming_conventions="Follow item naming conventions from campaign setting"
        ),
        
        EntityType.EVENT: EntityTemplate(
            entity_type=EntityType.EVENT,
            required_properties=["name", "description", "timeframe", "participants"],
            optional_properties=[
                "location", "outcome", "consequences",
                "duration", "casualties", "significance",
                "causes", "key_moments"
            ],
            generation_guidelines="""EVENT GENERATION GUIDELINES:

**Temporal Placement:**
- Place clearly in timeline (when did this happen?)
- Respect existing chronology (don't contradict established events)
- Consider what led to this event (causes) and what followed (consequences)

**Participants:**
- Reference existing factions/characters when possible
- Clear roles (who did what?)
- Motivations for involvement

**Consequences:**
- How did this event shape the present day?
- Ripple effects on locations, factions, characters
- Unresolved issues or ongoing impacts

**Scope & Scale:**
- Scale matches importance (personal tragedy vs realm-changing war)
- Appropriate duration and casualties for event type

**Significance to the world**

**Naming:**
- Descriptive and memorable
- Follow event naming patterns from setting
- Should indicate nature of event

**Quality Standards:**
- Events should feel earned, not arbitrary
- Clear cause and effect chains
- Leave some mysteries or unanswered questions for intrigue""",
            naming_conventions="Descriptive naming that indicates event nature"
        ),
        
        EntityType.CONCEPT: EntityTemplate(
            entity_type=EntityType.CONCEPT,
            required_properties=["name", "description", "type"],
            optional_properties=[
                "manifestation", "origin", "practitioners",
                "dangers", "limitations", "societal_view",
                "applications", "taboos"
            ],
            generation_guidelines="""CONCEPT GENERATION GUIDELINES:

**Definition & Boundaries:**
- Clear explanation of what this concept is
- How it manifests in the world
- What it can and cannot do (limitations)

**Power Systems:**
- For magic/technology/powers: clear rules and costs
- Consistency with world's established power systems
- Limitations prevent "solve everything" solutions

**Cultural Integration:**
- How does society view this concept?
- Who uses it and how?
- Taboos, restrictions, or regulations

**Mystery & Discovery:**
- Leave room for mystery (not fully explained)
- Potential for discovery or misunderstanding
- Should enable stories, not solve them

**Naming:**
- Abstract or evocative names
- Consistent with setting's terminology
- Should convey nature of concept

**Quality Standards:**
- Avoid overpowered or unlimited concepts
- Clear costs, drawbacks, or risks
- Should create interesting complications, not eliminate them""",
            naming_conventions="Abstract/evocative naming consistent with setting"
        )
    }
    
    @staticmethod
    def validate_entity(entity_data: Dict[str, Any], template: EntityTemplate) -> bool:
        """
        Validate entity has required properties.
        
        Args:
            entity_data: Entity to validate
            template: Template to validate against
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If required properties missing
        """
        properties = entity_data.get("properties", {})
        
        missing = [
            prop for prop in template.required_properties 
            if prop not in properties
        ]
        
        if missing:
            raise ValueError(
                f"Entity missing required properties: {missing}"
            )
        
        return True
    
    @staticmethod
    def get_template(entity_type: EntityType) -> EntityTemplate:
        """Get template for entity type."""
        return EntityFactory.TEMPLATES[entity_type]
    
    @staticmethod
    def create_entity_skeleton(
        entity_type: EntityType,
        name: str
    ) -> Dict[str, Any]:
        """
        Create entity skeleton with default values.
        Useful for testing or manual entity creation.
        """
        template = EntityFactory.TEMPLATES[entity_type]
        
        return {
            "name": name,
            "label": entity_type.value,
            "properties": {
                prop: "" for prop in template.required_properties
            }
        }

