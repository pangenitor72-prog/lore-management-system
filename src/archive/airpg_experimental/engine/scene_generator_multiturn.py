# src/airpg/engine/scene_generator_multiturn.py
from typing import Dict

def generate_scene(ocean: Dict[str, float]) -> str:
    # This scene demonstrates short-range personality coherence
    # across multiple conversational turns without persistence.

    npc_name = "Elara"
    location_description = (
        "The small alchemist's lab is a chaotic symphony of bubbling beakers, "
        "glowing retorts, and shelves overflowing with exotic herbs and dusty tomes. "
        "The air hums with faint, earthy aromas and a tangible sense of potent possibility."
    )
    # The player implicitly presents a strange, non-magical artifact.

    # --- Interpret OCEAN traits ---
    openness = ocean.get("openness", 0.5)
    conscientiousness = ocean.get("conscientiousness", 0.5)
    neuroticism = ocean.get("neuroticism", 0.5)

    scene = f"{location_description}\n\n"
    dialogue = []

    # --- Turn 1: Initial reaction to the artifact ---
    if openness > 0.7:
        dialogue.append(f"{npc_name}: (Eyes wide with wonder, leans closer) 'Oh, by the cosmic currents! What magnificent enigma have you brought to my humble sanctuary? Its very presence sings of untold histories, a silent testament to forgotten craft! Do you feel it? The whisper of innovation, perhaps even a failed endeavor that birthed something truly unique!'")
    elif openness < 0.3:
        dialogue.append(f"{npc_name}: (Frowns, takes the artifact carefully) 'Another trinket? Show me. Hmm. Cold metal. Odd shape. What is its function? I see no runes, no magical resonance. A mere curiosity, I presume.'")
    else: # Moderate openness
        dialogue.append(f"{npc_name}: (Tilts head, examines it with interest) 'Intriguing. Not of any common make I recognize. What is its origin? Its purpose?'")

    # --- Turn 2: Response to implied player query/challenge ---
    # Player implicitly asks for more info or challenges Elara's initial assessment.
    
    if openness > 0.7 and conscientiousness > 0.7: # High Openness, High Conscientiousness: Elaborates thoughtfully and methodically
        dialogue.append(f"{npc_name}: 'Ah, but a true alchemist knows that even the mundane holds secrets! I shall catalog its precise density, its thermal conductivity, its resonant frequency. Every detail is a thread in the tapestry of its being, leading us to understand not just what it is, but *why* it is.'")
    elif openness < 0.3 and neuroticism > 0.7: # Low Openness, High Neuroticism: Shuts down, gets defensive
        dialogue.append(f"{npc_name}: (Sighs, places the artifact down sharply) 'What do you want from me? It's just a thing. Some pointless mechanism. My work is far more important than dissecting your... curios. Leave it, or take it. I have no more to say on the matter.'")
    elif openness < 0.3 and conscientiousness > 0.7: # Low Openness, High Conscientiousness: Provides practical, concrete details
        dialogue.append(f"{npc_name}: 'Its composition appears to be a standard iron-carbon alloy, with traces of nickel. The surface hardness is consistent with cold forging. It is non-reactive to basic acids. Functionally, it remains unclear without further schematics.'")
    elif openness > 0.7 and neuroticism > 0.7: # High Openness, High Neuroticism: Spirals into anxious speculation
        dialogue.append(f"{npc_name}: 'But what if it's a trap? A beacon? A fragment of something that should not be? Every analysis could unleash untold... possibilities! We must be careful! What if *it's* analyzing *us*?!'")
    else: # Moderate traits
        dialogue.append(f"{npc_name}: 'I can attempt a basic material analysis, perhaps cross-reference its design with historical records. It will take time. There are no obvious magical properties, I assure you.'")

    # --- Turn 3: Final stance/action based on overall personality ---
    # Player implicitly asks for a clear conclusion or next steps.

    if conscientiousness > 0.7 and neuroticism < 0.3: # High Conscientiousness, Low Neuroticism: Proactive, organized conclusion
        dialogue.append(f"{npc_name}: 'Very well. I will dedicate the next few hours to a thorough investigation. Return at dusk, and I shall provide a comprehensive report, with all findings meticulously documented and cross-referenced. You may count on my diligence.'")
    elif conscientiousness < 0.3 and openness > 0.7: # Low Conscientiousness, High Openness: Enthusiastic but disorganized next steps
        dialogue.append(f"{npc_name}: 'Oh, this is marvelous! A grand new puzzle! I'll dive in immediately! Just... leave it anywhere. I'll find it when inspiration strikes. Or when I trip over it. Whichever comes first! Perhaps I'll discover a new elemental principle!'")
    elif neuroticism > 0.7: # High Neuroticism: Tries to disengage or express worry
        dialogue.append(f"{npc_name}: (Wrings hands) 'Please, just... take it. It feels wrong. It's too quiet. I don't need this kind of distraction right now. My current experiments are far too delicate to be disturbed by such... unknown variables.'")
    else: # Moderate
        dialogue.append(f"{npc_name}: 'I will examine it further. My findings will be inconclusive without more context, but I will do what I can. Check back tomorrow.'")

    scene += "\n\n".join(dialogue)
    return scene
