"""
Canonical Identity Policy & Normalization Logic
================================================

POLICY:
For any given entity type, there may exist only one canonical entity representing a real in-world concept.
All alternative spellings, formats, or aliases must resolve to the same canon_id.

This policy must be:
- Enforced programmatically (via this module)
- Auditable
- Deterministic

"""

import re

def normalize_entity_name(name: str) -> str:
    """
    Normalizes an entity name to a canonical form for identity comparison.
    
    Transformation rules:
    1. Convert to lowercase.
    2. Remove all whitespace.
    3. Remove all punctuation.
    
    Examples:
    - "Lead Corps" -> "leadcorps"
    - "LeadCorps" -> "leadcorps"
    - "Lead-Corps" -> "leadcorps"
    - "The  Lead   Corps." -> "theleadcorps"
    
    Args:
        name (str): The original entity name.
        
    Returns:
        str: The normalized name string.
    """
    if not name:
        return ""
        
    # Lowercase
    norm = name.lower()
    
    # Remove all non-alphanumeric characters (removes whitespace and punctuation)
    norm = re.sub(r'[^a-z0-9]', '', norm)
    
    return norm

