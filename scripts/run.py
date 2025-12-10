"""
Startup script for Lore Management System API
Ensures correct Python path and launches uvicorn
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now start uvicorn
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=9000,
        reload=True,
        reload_dirs=[str(project_root / "src")]
    )