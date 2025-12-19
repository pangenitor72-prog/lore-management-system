# src/airpg/engine/scene_generator_social_context.py
from typing import Dict

def generate_scene(ocean: Dict[str, float], role: str) -> str:
    # This scene demonstrates how identical personality
    # expresses differently under social role pressure
    # without modifying the underlying OCEAN profile.

    npc_name = "Kaelen"
    location_description = (
        "The small alchemist's lab is a chaotic symphony of bubbling beakers, "
        "glowing retorts, and shelves overflowing with exotic herbs and dusty tomes. "
        "The air hums with faint, earthy aromas and a tangible sense of potent possibility."
    )
    topic = "the peculiar, shimmering dust found near the old spire."

    # --- Interpret OCEAN traits ---
    agreeableness = ocean.get("agreeableness", 0.5)
    conscientiousness = ocean.get("conscientiousness", 0.5)
    extraversion = ocean.get("extraversion", 0.5)
    openness = ocean.get("openness", 0.5) # Used for language style

    scene = f"{location_description}\n\n"
    dialogue_a = ""
    dialogue_b = ""
    physical_action = ""

    # Behavior based on role and personality
    if role == "faction_representative":
        # Representative: more guarded, formal, focuses on faction's stance
        # Agreeableness (deference vs. dominance): less deferential, more authoritative
        # Conscientiousness (restraint/caution): very careful with words, avoids speculation
        # Extraversion (candor): less candid, speaks officially
        
        physical_action = f"{npc_name} stands straighter, his hands clasped formally behind his back. His eyes scan the lab, but his attention is fixed. "
        
        if conscientiousness > 0.7: # High conscientiousness: very formal, controlled
            dialogue_a = (
                f"'Regarding the {topic}, the Guild is aware of the reports. Our preliminary assessment "
                "indicates no immediate threat to public safety. Further investigation is underway. "
                "Any speculation beyond that is irresponsible and unhelpful.' He pauses, then adds, "
                "'Your cooperation in this matter, by refraining from disseminating unverified theories, "
                "would be appreciated.'"
            )
        elif conscientiousness < 0.3: # Low conscientiousness: still representative, but might show impatience
             dialogue_a = (
                f"'Yes, the dust. Look, the Guild is handling it. Don't worry your head about it. "
                "We'll issue a statement when there's something concrete. Just... don't make a fuss, alright?'"
             )
        else: # Moderate conscientiousness
            dialogue_a = (
                f"'The Guild is examining the {topic}. We are proceeding with due diligence. "
                "We advise caution and patience while our experts conduct their analysis. "
                "We will share pertinent information when it becomes available.'"
            )

        if agreeableness < 0.3 and extraversion > 0.7: # Low agreeableness, high extraversion: more dominant, less open to discussion
            physical_action += "He steps forward, subtly occupying more space. "
            dialogue_b = "'There is nothing more to discuss on this matter at present. Your role is to observe, not to interfere.'"
        elif agreeableness > 0.7 and extraversion < 0.3: # High agreeableness, low extraversion: still firm, but polite
            physical_action += "He offers a slight, reassuring nod. "
            dialogue_b = "'We appreciate your concern. Rest assured, proper protocols are being followed. We trust you understand the need for discretion.'"
        else: # Moderate
            dialogue_b = "'We must manage public perception responsibly. Please ensure your actions reflect the Guild's position.'"

    elif role == "private_individual":
        # Private individual: more candid, curious, less concerned with official stance
        # Agreeableness (deference vs. dominance): more deferential, less authoritative
        # Conscientiousness (restraint/caution): more open to speculation, less guarded
        # Extraversion (candor): more candid, shares thoughts openly
        
        physical_action = f"{npc_name} gestures wildly, nearly knocking over a beaker. 'The {topic}, you say?! "
        
        if openness > 0.7: # High openness: imaginative, philosophical language
            dialogue_a = (
                f"It's like stardust from a forgotten dream, isn't it? "
                "A whisper of something ancient waking up. I've been experimenting, "
                "but it resists all known categorizations! What if it's not dust at all, "
                "but solidified thought, a residue of intense emotion?'"
            )
        elif openness < 0.3: # Low openness: practical, grounded language
            dialogue_a = (
                f"It's just... glowing dust. Probably some rare mineral reacting to local atmospheric conditions. "
                "I've analyzed it, but its properties are elusive. No magical residue, just strange chemistry.'"
            )
        else: # Moderate openness
            dialogue_a = (
                f"It's fascinating, this {topic}. "
                "I'm trying to understand its fundamental properties. There's a subtle energy signature "
                "I can't quite place.'"
            )


        if agreeableness > 0.7 and extraversion > 0.7: # High agreeableness, high extraversion: eager to share, collaborative
            physical_action += "He pulls up a stool, inviting collaboration. "
            dialogue_b = "'Come, tell me your observations! Perhaps together we can unravel its secrets! Every perspective sheds new light!'"
        elif agreeableness < 0.3 and extraversion < 0.3: # Low agreeableness, low extraversion: skeptical, but still private
            physical_action += "He narrows his eyes, a flicker of suspicion. "
            dialogue_b = "'And what exactly do *you* stand to gain by inquiring about this? I guard my research closely.'"
        else: # Moderate
            dialogue_b = "'What have you heard? I'm always interested in new data, but beware of jumping to conclusions.'"
    else:
        # Default/Error case
        return f"Error: Unknown role '{role}' for NPC {npc_name}."

    scene += physical_action + dialogue_a + "\n\n" + dialogue_b
    return scene
