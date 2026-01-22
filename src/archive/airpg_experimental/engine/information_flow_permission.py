# src/airpg/engine/information_flow_permission.py
from typing import Dict, List, Optional

def propagate_with_personality(
    info: str,
    source: str,
    topology: Dict[str, List[str]],
    oceans: Dict[str, Dict[str, float]]
) -> Dict[str, Optional[str]]:
    # This function demonstrates deterministic information forwarding
    # gated by personality after topology has granted access.

    # --- Step 1: Determine reachability via topology (from Phase 4A) ---
    reachable_nodes = set()
    queue = [source]
    visited = {source}

    while queue:
        current_node = queue.pop(0)
        neighbors = topology.get(current_node, [])
        for neighbor in neighbors:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    
    reachable_nodes = visited

    # --- Step 2: Evaluate forwarding permission for each node based on personality ---
    forwarding_results = {}

    all_nodes = set(topology.keys())
    for sub_list in topology.values():
        all_nodes.update(sub_list)

    for node in all_nodes:
        if node == source:
            forwarding_results[node] = info # The source always has the original info
            continue

        if node not in reachable_nodes:
            forwarding_results[node] = None # Unreachable
            continue

        # This node is reachable, now apply personality gate
        npc_ocean = oceans.get(node, {})
        conscientiousness = npc_ocean.get("conscientiousness", 0.5)
        extraversion = npc_ocean.get("extraversion", 0.5)
        neuroticism = npc_ocean.get("neuroticism", 0.5)
        agreeableness = npc_ocean.get("agreeableness", 0.5)

        # --- Personality Gating Logic ---
        # High conscientiousness, low neuroticism: reliable forwarder
        if conscientiousness > 0.8 and neuroticism < 0.2:
            forwarding_results[node] = f"[ACCURATE] {info}"
        
        # High neuroticism, low conscientiousness: halts out of fear/uncertainty
        elif neuroticism > 0.8 and conscientiousness < 0.3:
            forwarding_results[node] = "[HALTED - FEAR]"
        
        # Low agreeableness, low extraversion: halts out of apathy
        elif agreeableness < 0.2 and extraversion < 0.2:
            forwarding_results[node] = "[HALTED - APATHY]"
            
        # High extraversion, high neuroticism: forwards with amplification
        elif extraversion > 0.8 and neuroticism > 0.7:
            forwarding_results[node] = f"[AMPLIFIED] It's a disaster! I'm telling you, {info.lower()} and it's probably even worse than it sounds!"

        # Default forwarding for other personalities, may have slight framing
        else:
            if agreeableness > 0.7:
                forwarding_results[node] = f"[CAUTIOUS] I heard that {info.lower()}, for what it's worth."
            elif extraversion > 0.7:
                forwarding_results[node] = f"[BROADCAST] Urgent news: {info}."
            else:
                 forwarding_results[node] = f"{info}" # Forwards unchanged

    return forwarding_results
