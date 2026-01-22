# src/airpg/engine/information_stability.py
from typing import Dict, List

def stabilize_or_amplify(info_chain: List[str], ocean: Dict[str, float]) -> str:
    # This function demonstrates deterministic belief stabilization
    # versus amplification driven by personality alone.

    # --- Interpret OCEAN traits ---
    neuroticism = ocean.get("neuroticism", 0.5)
    conscientiousness = ocean.get("conscientiousness", 0.5)
    extraversion = ocean.get("extraversion", 0.5)
    agreeableness = ocean.get("agreeableness", 0.5)

    # --- Extract relevant information from chain ---
    # Assuming info_chain[0] is the most "factual" or original version.
    # The last item in the chain is the result of accumulated drift.
    original_fact = info_chain[0]
    drifted_info = info_chain[-1] if len(info_chain) > 1 else original_fact
    
    final_framing = ""

    # --- Decision logic based on personality ---

    # High Conscientiousness + Low Neuroticism = Stabilize
    if conscientiousness > 0.7 and neuroticism < 0.3:
        # Stabilize: lean towards original fact, correct exaggerations
        if "disaster" in drifted_info or "ruin" in drifted_info:
            final_framing = f"Let's not get carried away. The facts are: {original_fact.replace('A', 'a')}."
        elif "late" in drifted_info or "delayed" in drifted_info:
            final_framing = f"The core of the matter is simply that {original_fact.lower().replace('a shipment', 'the shipment')}."
        else:
            final_framing = f"The situation is precisely: {original_fact.lower().replace('a shipment', 'the shipment')}."
        
        # Add agreeableness influence
        if agreeableness > 0.7:
            final_framing = f"While I understand concerns, {final_framing}"
        else:
            final_framing = f"Frankly, {final_framing}"

    # High Neuroticism + High Extraversion = Amplify
    elif neuroticism > 0.7 and extraversion > 0.7:
        # Amplify: lean towards emotional, dramatic, urgent framing
        if "disaster" in drifted_info:
            final_framing = f"It's a full-blown catastrophe! Just as I feared! {drifted_info.capitalize()}"
        elif "late" in drifted_info or "delayed" in drifted_info:
            final_framing = f"This isn't just a delay, it's a symptom! A terrible omen! {drifted_info.capitalize()} and who knows what else is coming!"
        else:
            final_framing = f"Everyone needs to know! This is bigger than it looks! {drifted_info.capitalize()}!"
        
        # Add agreeableness influence
        if agreeableness < 0.3:
            final_framing = f"Don't you see?! {final_framing}"
        else:
            final_framing = f"I'm afraid I must convey the urgency: {final_framing}"

    # Mixed or other profiles: cautious framing, partial correction
    else:
        # Neutral or cautious framing
        if "disaster" in drifted_info and conscientiousness > 0.5:
            final_framing = f"Reports suggest it might be a problem. {original_fact.replace('A', 'A shipment')} seems to be the core issue."
        elif "late" in drifted_info and neuroticism > 0.5:
            final_framing = f"There's some concern about the delay: {original_fact.replace('A', 'a')}."
        else:
            final_framing = f"The information circulating is that {drifted_info.lower()}."
            
        # Extraversion influence on hesitancy/directness
        if extraversion < 0.3:
            final_framing = f"I'm not entirely sure, but {final_framing}"
        elif extraversion > 0.7:
            final_framing = f"Here's what I know: {final_framing}"
        
        # Agreeableness to soften or add politeness
        if agreeableness > 0.7:
            final_framing = f"With all due respect, {final_framing}"
        elif agreeableness < 0.3:
            final_framing = f"Let's be clear. {final_framing}"

    # Clean up any extra spacing
    return " ".join(final_framing.split())
