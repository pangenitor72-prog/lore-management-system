# This file exists solely as a Phase 4C validation artifact and is not part of
# the runtime engine.

# src/airpg/engine/information_saturation.py
from typing import Dict, List

def propagate_until_stop(
    info: str,
    source: str,
    topology: Dict[str, List[str]],
    oceans: Dict[str, Dict[str, float]],
    max_steps: int
) -> List[Dict[str, str]]:
    # This function demonstrates deterministic propagation that either saturates
    # or terminates based on topology and personality gates alone.

    # --- Initialization ---
    step_snapshots = [{source: info}]
    all_informed_nodes = {source}
    
    # Nodes that just received info in the previous step and will be processed in the current one
    nodes_to_process_in_this_step = {source: info}
    
    for _ in range(max_steps):
        next_step_deliveries = {}

        # Process each node that received info in the last step
        for forwarding_node, received_info in nodes_to_process_in_this_step.items():
            
            # --- Personality Gate ---
            node_ocean = oceans.get(forwarding_node, {})
            neuroticism = node_ocean.get("neuroticism", 0.5)
            conscientiousness = node_ocean.get("conscientiousness", 0.5)
            extraversion = node_ocean.get("extraversion", 0.5)
            agreeableness = node_ocean.get("agreeableness", 0.5)

            # Apply deterministic forwarding rules
            forwards = True
            forwarded_info = received_info
            
            if neuroticism > 0.8 and conscientiousness < 0.3:
                forwards = False
            elif agreeableness < 0.2 and extraversion < 0.2:
                forwards = False
            elif conscientiousness > 0.8 and neuroticism < 0.2:
                forwarded_info = f"[ACCURATE] {received_info}"
            elif extraversion > 0.8 and neuroticism > 0.7:
                forwarded_info = f"[AMPLIFIED] {received_info}"
            # else: forwards unchanged

            if not forwards:
                continue # This node halts propagation

            # --- Topology Gate ---
            # If the node forwards, find its reachable neighbors
            neighbors = topology.get(forwarding_node, [])
            
            for neighbor in neighbors:
                # Deliver only if the neighbor has not been informed yet
                if neighbor not in all_informed_nodes:
                    next_step_deliveries[neighbor] = forwarded_info
                    all_informed_nodes.add(neighbor)

        # --- Termination/Saturation Check ---
        if not next_step_deliveries:
            break # No new nodes were informed, propagation terminates

        step_snapshots.append(next_step_deliveries)
        nodes_to_process_in_this_step = next_step_deliveries

    return step_snapshots
