"""Build the Zero-to-Hero Enterprise Copilot notebook.

    python scripts/build_copilot.py
"""
from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import copilot_a, copilot_b, copilot_c, copilot_d
from copilot_common import save

CONTROL_CHARS = {"\x08": r"\b", "\x0c": r"\f", "\x07": r"\a", "\x0b": r"\v"}


def check_escapes(cells) -> None:
    """Fail the build on a mangled regex escape.

    The generator writes cell source inside NON-raw triple-quoted strings, so a
    lone `\b` in a regex becomes a literal backspace before it ever reaches the
    notebook -- and the resulting pattern silently never matches. It cost one
    debugging session to find; this makes it impossible to ship again.
    Write `\\b` in the generator, always.
    """
    problems = []
    for i, cell in enumerate(cells):
        src = "".join(cell["source"])
        for ch, name in CONTROL_CHARS.items():
            if ch in src:
                line = next(l for l in src.splitlines() if ch in l)
                problems.append(f"  cell {i}: literal {name} control char -> {line.strip()[:70]}")
    if problems:
        raise SystemExit("MANGLED ESCAPES (use \\ in the generator):\n" + "\n".join(problems))


def main() -> None:
    cells = (copilot_a.build() + copilot_b.build()
             + copilot_c.build() + copilot_d.build())
    check_escapes(cells)
    path = save(cells)
    n_code = sum(1 for c in cells if c["cell_type"] == "code")
    print(f"built {os.path.basename(path)}")
    print(f"  {len(cells)} cells ({n_code} code, {len(cells) - n_code} markdown)")

if __name__ == "__main__":
    main()
