"""Narrative generation helpers for mechanical results."""

import random
from typing import List, Optional
from ..engine.combat_resolver import AttackResult, DamageResult, DamageType
from ..engine.checks import CheckResult


class NarrationHelper:
    """
    Translates mechanical outcomes into narrative descriptions.

    Used by the DM agent to incorporate mechanical results into story.
    """

    # Attack outcome narratives
    ATTACK_NARRATIVES = {
        "critical_hit": [
            "strikes with devastating precision",
            "finds a gap in their defenses",
            "lands a crushing blow",
            "delivers a perfect strike",
            "catches them completely off guard",
        ],
        "hit": [
            "connects solidly",
            "strikes true",
            "lands a blow",
            "finds their mark",
            "hits their target",
        ],
        "miss": [
            "swings wide",
            "is deflected",
            "fails to connect",
            "misses their target",
            "strikes only air",
        ],
        "critical_miss": [
            "stumbles badly",
            "completely misjudges",
            "leaves themselves exposed",
            "fumbles the attack",
            "swings wildly off-target",
        ],
    }

    # Damage type flavor
    DAMAGE_FLAVOR = {
        DamageType.SLASHING: ["cuts", "slashes", "carves", "slices"],
        DamageType.PIERCING: ["stabs", "pierces", "punctures", "impales"],
        DamageType.BLUDGEONING: ["crushes", "smashes", "batters", "pounds"],
        DamageType.FIRE: ["burns", "scorches", "ignites", "sears"],
        DamageType.COLD: ["freezes", "chills", "frosts", "numbs"],
        DamageType.LIGHTNING: ["shocks", "electrifies", "jolts", "zaps"],
        DamageType.RADIANT: ["sears with holy light", "burns with radiance", "illuminates"],
        DamageType.NECROTIC: ["withers", "drains", "corrupts", "decays"],
        DamageType.FORCE: ["blasts", "impacts", "slams", "strikes"],
        DamageType.POISON: ["poisons", "sickens", "envenoms"],
        DamageType.ACID: ["corrodes", "dissolves", "burns with acid"],
        DamageType.PSYCHIC: ["assaults the mind of", "mentally attacks", "psychically damages"],
        DamageType.THUNDER: ["deafens", "concusses", "thunderously strikes"],
    }

    # Skill check flavor by skill
    SKILL_FLAVOR = {
        "stealth": {
            "success": ["moves silently", "slips past unnoticed", "melts into the shadows"],
            "failure": ["makes too much noise", "is spotted", "stumbles noisily"],
        },
        "perception": {
            "success": ["notices", "spots", "catches sight of", "perceives"],
            "failure": ["misses", "overlooks", "fails to notice"],
        },
        "persuasion": {
            "success": ["convinces", "persuades", "wins over"],
            "failure": ["fails to convince", "comes across as unconvincing"],
        },
        "athletics": {
            "success": ["powers through", "muscles their way", "succeeds with strength"],
            "failure": ["strains but fails", "can't quite manage"],
        },
        "acrobatics": {
            "success": ["nimbly", "gracefully", "with agile precision"],
            "failure": ["loses balance", "tumbles awkwardly"],
        },
        "insight": {
            "success": ["senses", "perceives the truth", "reads between the lines"],
            "failure": ["can't get a read", "misreads the situation"],
        },
    }

    @classmethod
    def narrate_attack(cls, result: AttackResult) -> str:
        """Generate narrative description of an attack."""
        if result.is_critical:
            return random.choice(cls.ATTACK_NARRATIVES["critical_hit"])
        elif result.is_critical_miss:
            return random.choice(cls.ATTACK_NARRATIVES["critical_miss"])
        elif result.is_hit:
            return random.choice(cls.ATTACK_NARRATIVES["hit"])
        else:
            return random.choice(cls.ATTACK_NARRATIVES["miss"])

    @classmethod
    def narrate_damage(
        cls,
        result: DamageResult,
        target_name: str = "them",
    ) -> str:
        """Generate narrative description of damage dealt."""
        damage_verbs = cls.DAMAGE_FLAVOR.get(
            result.damage_type,
            ["damages"]
        )
        verb = random.choice(damage_verbs)

        # Severity description
        if result.damage_total >= 20:
            severity = "critically"
        elif result.damage_total >= 12:
            severity = "heavily"
        elif result.damage_total >= 6:
            severity = ""
        else:
            severity = "lightly"

        if severity:
            return f"{severity} {verb} {target_name}"
        return f"{verb} {target_name}"

    @classmethod
    def narrate_check(
        cls,
        result: CheckResult,
        action_description: Optional[str] = None,
    ) -> str:
        """Generate narrative description of a skill/ability check."""
        skill = result.skill_used or result.ability_used

        if skill and skill in cls.SKILL_FLAVOR:
            flavor = cls.SKILL_FLAVOR[skill]
            if result.success:
                return random.choice(flavor["success"])
            else:
                return random.choice(flavor["failure"])

        # Generic fallback
        if result.narrative_outcome == "critical_success":
            return "succeeds brilliantly"
        elif result.narrative_outcome == "success":
            return "succeeds"
        elif result.narrative_outcome == "close_success":
            return "barely manages"
        elif result.narrative_outcome == "close_failure":
            return "almost succeeds"
        elif result.narrative_outcome == "failure":
            return "fails"
        else:  # critical_failure
            return "fails completely"

    @classmethod
    def build_combat_sentence(
        cls,
        attacker_name: str,
        target_name: str,
        attack_result: AttackResult,
        damage_result: Optional[DamageResult] = None,
        weapon_name: Optional[str] = None,
    ) -> str:
        """Build a complete combat sentence."""
        weapon = weapon_name or "their weapon"
        attack_narration = cls.narrate_attack(attack_result)

        if not attack_result.is_hit:
            return f"{attacker_name} swings {weapon} at {target_name} but {attack_narration}."

        sentence = f"{attacker_name} {attack_narration} with {weapon}"

        if damage_result:
            damage_narration = cls.narrate_damage(damage_result, target_name)
            sentence += f", {damage_narration}"

        return sentence + "."

    @classmethod
    def get_injury_description(cls, current_hp: int, max_hp: int) -> str:
        """Describe a character's injury state narratively."""
        ratio = current_hp / max_hp if max_hp > 0 else 0

        if ratio >= 1.0:
            return "uninjured"
        elif ratio >= 0.75:
            return "lightly wounded"
        elif ratio >= 0.50:
            return "wounded"
        elif ratio >= 0.25:
            return "badly wounded"
        elif ratio > 0:
            return "barely standing"
        else:
            return "unconscious"

    @classmethod
    def get_contextual_hint(
        cls,
        check_result: Optional[CheckResult] = None,
        attack_result: Optional[AttackResult] = None,
    ) -> str:
        """
        Generate a contextual hint for Guided visibility mode.

        These hints help players understand the mechanics without
        showing raw numbers.
        """
        if check_result:
            if check_result.is_natural_20:
                return "A perfect moment of skill!"
            elif check_result.is_natural_1:
                return "An unfortunate fumble..."
            elif check_result.margin >= 5:
                return "Your abilities served you well"
            elif check_result.margin >= 0:
                return "You managed, but it was close"
            elif check_result.margin >= -5:
                return "You came close, but not quite"
            else:
                return "This task was beyond your current skill"

        if attack_result:
            if attack_result.is_critical:
                return "A devastating strike!"
            elif attack_result.is_critical_miss:
                return "A clumsy swing leaves you off-balance"
            elif attack_result.is_hit:
                return "Your training pays off"
            else:
                return "Your opponent's defenses hold"

        return ""
