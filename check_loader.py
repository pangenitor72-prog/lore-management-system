
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from src.mantle.dnd5e.data.loader import get_srd_loader

try:
    loader = get_srd_loader()
    equipment = loader.get_all_equipment()
    
    print(f"Equipment Keys: {list(equipment.keys())}")
    
    if not equipment:
        print("ERROR: Equipment dict is empty!")
    elif "weapons" not in equipment:
        print("ERROR: 'weapons' key missing from equipment!")
    else:
        print(f"Weapons count: {len(equipment.get('weapons', {}))}")
        print("SUCCESS: Equipment loaded correctly.")

except Exception as e:
    print(f"EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
