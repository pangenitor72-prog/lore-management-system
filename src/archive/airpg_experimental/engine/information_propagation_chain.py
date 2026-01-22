# src/airpg/engine/information_propagation_chain.py
from typing import Dict, List

def propagate_chain(info: str, oceans: List[Dict[str, float]]) -> List[str]:
    # This function demonstrates deterministic multi-hop information drift
    # driven by sequential personality filters without state or randomness.
    
    information_chain = [info]
    
    current_info = info
    
    for ocean_profile in oceans:
        # --- Interpret OCEAN traits ---
        neuroticism = ocean_profile.get("neuroticism", 0.5)
        conscientiousness = ocean_profile.get("conscientiousness", 0.5)
        openness = ocean_profile.get("openness", 0.5)
        agreeableness = ocean_profile.get("agreeableness", 0.5)
        
        # --- Frame the information based on personality ---
        # The order of these checks matters as they build on each other.
        
        # 1. Openness: Adds interpretive flourish or strips to literal facts.
        if openness > 0.8:
            # High openness adds a metaphorical or interpretive layer.
            current_info = f"I'm getting a sense that {current_info.lower()}, like a candle suddenly extinguished."
        elif openness < 0.2:
            # Low openness strips the information to its most basic components.
            if "shipment" in current_info and "failed to arrive" in current_info:
                current_info = "The shipment is late."

        # 2. Conscientiousness: Adds precision or introduces sloppiness/omission.
        if conscientiousness > 0.8:
            # High conscientiousness tries to add clarifying details (even if they weren't there).
            if "shipment is late" in current_info:
                current_info = "The specific manifest designated for the eastern gate is delayed."
        elif conscientiousness < 0.3:
            # Low conscientiousness might omit key details.
            if "eastern gate" in current_info:
                current_info = current_info.replace(" at the eastern gate", "") # Omits location.

        # 3. Neuroticism: Adds urgency, fear, or dismissive calm.
        if neuroticism > 0.8:
            # High neuroticism frames it as a catastrophe.
            current_info = f"This is a disaster! {current_info.capitalize()}! This could ruin everything!"
        elif neuroticism < 0.2:
            # Low neuroticism downplays the severity.
            if "disaster" not in current_info and "late" in current_info:
                current_info = f"It seems {current_info.lower()}, but I'm sure it's nothing to worry about."

        # 4. Agreeableness: Softens the message or makes it more blunt/accusatory.
        if agreeableness > 0.8:
            # High agreeableness softens the blow.
            current_info = f"I don't want to alarm anyone, but I heard that {current_info.lower()}"
        elif agreeableness < 0.2:
            # Low agreeableness makes it sound like an accusation or a blunt command.
            current_info = f"So, get this: {current_info}. Someone needs to answer for that."

        current_info = " ".join(current_info.split()) # Clean up potential spacing
        information_chain.append(current_info)
        
    return information_chain