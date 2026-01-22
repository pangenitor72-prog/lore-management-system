"""
d20 Rules Engine data models.

Provides both generic terminology (Origin, Archetype, Ability) and
backward-compatible D&D 5e aliases (Race, Class, Spell).
"""

from .ability_scores import AbilityScores, AbilityName

# Generic models (preferred for new code)
from .origins import (
    OriginData,
    ORIGINS_BY_GENRE,
    FANTASY_ORIGINS,
    SCIFI_ORIGINS,
    MODERN_ORIGINS,
    get_origin,
    get_origins_for_genre,
    # Backward compatible
    RaceName,
    RaceData,
    RACES,
    get_race,
    get_all_races,
)

from .archetypes import (
    ArchetypeData,
    HitDie,
    ARCHETYPES_BY_GENRE,
    FANTASY_ARCHETYPES,
    SCIFI_ARCHETYPES,
    MODERN_ARCHETYPES,
    get_archetype,
    get_archetypes_for_genre,
    get_starting_hp,
    get_hp_at_level,
    # Backward compatible
    ClassName,
    ClassData,
    CLASSES,
    get_class,
    get_all_classes,
)

from .abilities import (
    AbilityData,
    AbilityType,
    TargetType,
    ABILITIES_BY_GENRE,
    FANTASY_ABILITIES,
    SCIFI_ABILITIES,
    MODERN_ABILITIES,
    get_ability,
    get_abilities_for_genre,
    get_abilities_for_archetype,
    get_cantrips_for_archetype,
    # Backward compatible
    Spell,
    SPELLS,
    get_spell,
    get_all_spells,
)

from .character_sheet import CharacterSheet

from .features import (
    FeatureData,
    UseType,
    EffectType,
    ResourcePool,
    ResourcePoolData,
    CORE_FEATURES,
    RESOURCE_POOLS_BY_GENRE,
    FEATURE_TRANSLATIONS,
    ARCHETYPE_FEATURES,
    get_feature,
    get_features_for_archetype,
    get_resource_pool,
    get_all_resource_pools,
    translate_resource_pool_name,
    get_features_for_archetype_at_level,
    get_new_features_at_level,
)

__all__ = [
    # Core
    "AbilityScores",
    "AbilityName",
    "CharacterSheet",
    "HitDie",

    # Generic origin terms
    "OriginData",
    "ORIGINS_BY_GENRE",
    "FANTASY_ORIGINS",
    "SCIFI_ORIGINS",
    "MODERN_ORIGINS",
    "get_origin",
    "get_origins_for_genre",

    # Generic archetype terms
    "ArchetypeData",
    "ARCHETYPES_BY_GENRE",
    "FANTASY_ARCHETYPES",
    "SCIFI_ARCHETYPES",
    "MODERN_ARCHETYPES",
    "get_archetype",
    "get_archetypes_for_genre",
    "get_starting_hp",
    "get_hp_at_level",

    # Generic ability terms
    "AbilityData",
    "AbilityType",
    "TargetType",
    "ABILITIES_BY_GENRE",
    "FANTASY_ABILITIES",
    "SCIFI_ABILITIES",
    "MODERN_ABILITIES",
    "get_ability",
    "get_abilities_for_genre",
    "get_abilities_for_archetype",
    "get_cantrips_for_archetype",

    # Backward compatible D&D 5e aliases
    "RaceName",
    "RaceData",
    "RACES",
    "get_race",
    "get_all_races",
    "ClassName",
    "ClassData",
    "CLASSES",
    "get_class",
    "get_all_classes",
    "Spell",
    "SPELLS",
    "get_spell",
    "get_all_spells",

    # Features (class abilities)
    "FeatureData",
    "UseType",
    "EffectType",
    "ResourcePool",
    "ResourcePoolData",
    "CORE_FEATURES",
    "RESOURCE_POOLS_BY_GENRE",
    "FEATURE_TRANSLATIONS",
    "ARCHETYPE_FEATURES",
    "get_feature",
    "get_features_for_archetype",
    "get_resource_pool",
    "get_all_resource_pools",
    "translate_resource_pool_name",
    "get_features_for_archetype_at_level",
    "get_new_features_at_level",
]
