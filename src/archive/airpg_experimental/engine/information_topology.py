# src/airpg/engine/information_topology.py
from typing import Dict, List, Optional

def propagate_with_topology(
    info: str,
    source: str,
    topology: Dict[str, List[str]],
    recipients: List[str]
) -> Dict[str, Optional[str]]:
    # This function demonstrates deterministic information reachability
    # constrained by topology alone, independent of personality or state.

    reachable = set()
    queue = [source]
    visited = {source}

    # Perform a graph traversal (BFS-like) to find all reachable nodes from the source
    while queue:
        current_node = queue.pop(0)
        # Add current_node to reachable if it's one of the target recipients
        # No, we need to add all reachable, then check against recipients later

        neighbors = topology.get(current_node, [])
        for neighbor in neighbors:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    
    reachable = visited # All nodes reachable from source

    result = {}
    for recipient in recipients:
        if recipient in reachable:
            result[recipient] = info
        else:
            result[recipient] = None
            
    return result
