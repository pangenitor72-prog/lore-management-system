# This file exists solely as a Phase 1 validation artifact and is not part of
# the runtime engine.

from typing import Dict

def generate_scene(ocean_a: Dict[str, float], ocean_b: Dict[str, float]) -> str:
    # --- Fixed Scene Setup ---
    npc_a_name = "Kaelen"
    npc_b_name = "Valerius"
    location_description = (
        "The stark, metal-paneled briefing room is silent. A large tactical map "
        "glows on the central table, casting long shadows. Kaelen is tracing one of "
        "the glowing lines with a curious finger, while Valerius stands rigidly opposite, "
        "arms crossed, a storm brewing in his eyes."
    )

    # --- Trait Interpretation ---
    # NPC A (Kaelen)
    extraversion_a = ocean_a.get("extraversion", 0.5)
    agreeableness_a = ocean_a.get("agreeableness", 0.5)
    openness_a = ocean_a.get("openness", 0.5)

    # NPC B (Valerius)
    extraversion_b = ocean_b.get("extraversion", 0.5)
    agreeableness_b = ocean_b.get("agreeableness", 0.5)
    openness_b = ocean_b.get("openness", 0.5)

    # --- Scene Construction ---
    scene = f"{location_description}\n\n"
    dialogue = []

    # Part 1: Initial Statement (Dominance/Initiative)
    # The more extraverted character speaks first and sets the initial tone.
    if extraversion_a > extraversion_b:
        if openness_a > 0.7:
            dialogue.append(f"{npc_a_name}: (Softly) 'It's fascinating, isn't it? These lines... they aren't just borders. They're echoes of forgotten agreements, arteries of intent. What story does this map *truly* tell, Commander?'")
        else:
            dialogue.append(f"{npc_a_name}: 'Let's begin. The situation is complex, and we need to consider all angles before acting.'")
    else:
        if openness_b < 0.3:
            dialogue.append(f"{npc_b_name}: (Sharply) 'The objective is point A to point B. The line is a vector, not a story. Let's dispense with the philosophy, Kaelen, and focus on the tactical reality.'")
        else:
            dialogue.append(f"{npc_b_name}: 'We should review the primary objective. The plan is clear, and we must adhere to it.'")

    # Part 2: The Interruption (Collision of Agreeableness and Extraversion)
    # A highly extraverted, low-agreeableness character will interrupt a less extraverted one.
    # The response is dictated by the interrupted character's agreeableness.
    
    # Assume Speaker 2 tries to make a point.
    speaker_2_name = npc_b_name if extraversion_a > extraversion_b else npc_a_name
    interrupter_name = npc_a_name if extraversion_a > extraversion_b else npc_b_name
    
    interrupter_extraversion = extraversion_a if interrupter_name == npc_a_name else extraversion_b
    interrupter_agreeableness = agreeableness_a if interrupter_name == npc_a_name else agreeableness_b
    
    speaker_2_agreeableness = agreeableness_b if speaker_2_name == npc_b_name else agreeableness_a

    interruption_occurs = interrupter_extraversion > 0.7 and interrupter_agreeableness < 0.3
    
    if interruption_occurs:
        # The interruption happens.
        if speaker_2_agreeableness > 0.7:
            # The interrupted character concedes gracefully.
            dialogue.append(f"{speaker_2_name}: 'But if we consider—'")
            dialogue.append(f"{interrupter_name}: 'No. The time for consideration is past. The time for action is now. The plan is set.'")
            dialogue.append(f"{speaker_2_name}: (A quiet sigh) '...As you say.'")
        elif speaker_2_agreeableness < 0.3:
            # The interrupted character pushes back.
            dialogue.append(f"{speaker_2_name}: 'If you would allow me to finish—'")
            dialogue.append(f"{interrupter_name}: 'I have the strategy, you have your... theories. Stick to them.'")
            dialogue.append(f"{speaker_2_name}: (Voice hardens) 'My 'theories' have saved your soldiers more than once, Commander. You will listen.'")
        else:
            # Moderate agreeableness leads to a tense pause.
            dialogue.append(f"{speaker_2_name}: 'However, the secondary factor—'")
            dialogue.append(f"{interrupter_name}: 'The secondary factor is irrelevant until the primary is secured.'")
            dialogue.append(f"{speaker_2_name}: (Holds up a hand, pausing) 'Is it? Or does it change the very nature of the primary?'")
    else:
        # No interruption, a more standard turn-based exchange.
        if openness_a > 0.7 and openness_b < 0.3:
             dialogue.append(f"{npc_a_name}: 'Think of the possibilities, the unforeseen connections!'")
             dialogue.append(f"{npc_b_name}: 'I think of the facts. The terrain, the numbers. Stick to the facts.'")
        else:
            dialogue.append(f"{npc_a_name}: 'My approach is different, but valid.'")
            dialogue.append(f"{npc_b_name}: 'Your approach is noted. Now, back to the plan.'")


    scene += "\n".join(dialogue)
    return scene
