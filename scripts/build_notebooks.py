"""Build all six session notebooks from the per-notebook modules.

    python scripts/build_notebooks.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nb01, nb02, nb03, nb04, nb05, nb06
from nbtools import save

MODULES = [nb01, nb02, nb03, nb04, nb05, nb06]


def main() -> None:
    for mod in MODULES:
        path = save(mod.FILE, mod.build())
        import json
        cells = json.load(open(path))["cells"]
        code_cells = sum(1 for c in cells if c["cell_type"] == "code")
        print(f"  {mod.FILE:<34} {len(cells):>3} cells ({code_cells} code)")
    print("\nbuilt", len(MODULES), "notebooks")


if __name__ == "__main__":
    main()
