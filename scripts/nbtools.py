"""Helpers for building the session notebooks as .ipynb JSON.

Notebooks are generated rather than hand-edited so that the shared cells — the
Colab badge, the bootstrap, the API-key check — stay identical across all six.
In a live session, "notebook 4's bootstrap is subtly different" is a ten-minute
detour nobody planned for.

    python scripts/build_notebooks.py
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

# INSTRUCTOR: change this to your fork before publishing. It is the SINGLE
# source for the "Open in Colab" badge, the bootstrap cell's git clone URL and
# the Colab sys.path entry — deriving all three from one constant is why a
# rename cannot leave two of them pointing somewhere that 404s.
REPO = "baluragala/genai_system_architecture_and_behaviour"
REPO_NAME = REPO.split("/")[-1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_DIR = os.path.join(ROOT, "notebooks")


def md(text: str) -> Dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def _render(text: str) -> str:
    """Substitute repo tokens. Not an f-string: BOOTSTRAP contains dict literals,
    and `.format()` would choke on every brace in them."""
    return text.replace("__REPO_NAME__", REPO_NAME).replace("__REPO__", REPO)


def code(text: str) -> Dict[str, Any]:
    text = _render(text)
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    }


def _lines(text: str) -> List[str]:
    text = text.strip("\n")
    lines = text.split("\n")
    return [l + "\n" for l in lines[:-1]] + [lines[-1]]


def badge(filename: str) -> Dict[str, Any]:
    url = f"https://colab.research.google.com/github/{REPO}/blob/main/notebooks/{filename}"
    return md(f"[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]({url})")


BOOTSTRAP = '''
# ============================================================
# BOOTSTRAP — run this cell first. (Identical in every notebook.)
# ============================================================
# Works in Colab, a local venv, or a bare Jupyter. It installs only what is
# actually MISSING — checking by import is the only reliable test, because
# "am I in Colab?" tells you nothing about what is already installed.
import importlib.util, os, subprocess, sys

IN_COLAB = "google.colab" in sys.modules
REPO_URL = "https://github.com/__REPO__.git"

REQUIRED = {          # import name -> pip package name
    "openai":   "openai",
    "PIL":      "pillow",
    "mcp":      "mcp>=2,<3",   # the SDK renamed its server API between majors
}

def _present(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False

missing = sorted({pkg for mod, pkg in REQUIRED.items() if not _present(mod)})
if missing:
    print("installing:", ", ".join(missing))
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *missing], check=False)
else:
    print("dependencies: all present")

try:
    import meridian
except ModuleNotFoundError:
    if IN_COLAB:
        subprocess.run(["git", "clone", "-q", REPO_URL], check=False)
        sys.path.insert(0, "/content/__REPO_NAME__")
    else:
        sys.path.insert(0, os.path.abspath(".."))
    import meridian

print("meridian", meridian.__version__, "| colab:", IN_COLAB)
'''

APIKEY = '''
# ============================================================
# YOUR API KEY  (required — there is no offline fallback)
# ============================================================
# Every notebook in this session calls a REAL model. That is deliberate: a
# simulated model can show you the SHAPE of a layered system while quietly
# misrepresenting the one property the whole session is about — that this
# component is probabilistic. Notebook 02 runs the same claim ten times and
# counts the disagreements. A stub would answer identically every time and
# teach you a comfortable lie.
#
#   Colab : sidebar -> key icon -> add a secret named OPENAI_API_KEY
#           -> toggle "Notebook access" ON -> re-run this cell
#   local : export OPENAI_API_KEY=sk-...   then restart the kernel
from meridian import current_config, get_llm

llm = get_llm()
print(current_config())
print("active model:", llm.name)
print()
print("These notebooks spend real money. The whole session is a few cents at")
print("gpt-4o-mini prices; the trace prints the running cost as you go.")
'''


def header(title: str, subtitle: str, duration: str, mode: str, where: str,
           takeaway: str) -> Dict[str, Any]:
    return md(f'''
# GenAI System Architecture & Behaviour
## {title}
**Duration:** {duration} &nbsp;|&nbsp; **Mode:** {mode}

> {subtitle}

![stack](https://dummyimage.com/1000x64/0f172a/ffffff&text=L1+Interface+%E2%86%92+L2+Orchestration+%E2%86%92+L3+Context+%E2%86%92+L4+Model+%E2%86%92+L5+Tools+%E2%86%92+L6+Validation+%E2%86%92+L7+Observability)

**Where we are in the stack:** {where}

> ### The takeaway for this notebook
> {takeaway}

> **Requires `OPENAI_API_KEY`.** These notebooks call a real model — there is
> no simulated fallback, on purpose.
''')


def predict(question: str) -> Dict[str, Any]:
    """A prediction prompt. Being wrong out loud is the lesson."""
    return md(f"> ### ✋ Predict before you run\n> {question}\n>\n> Write your answer down. Then run the cell.")


def notebook(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "colab": {"provenance": [], "toc_visible": True},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def save(filename: str, cells: List[Dict[str, Any]]) -> str:
    os.makedirs(NB_DIR, exist_ok=True)
    path = os.path.join(NB_DIR, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(notebook(cells), fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return path


def standard_opening(filename: str, title: str, subtitle: str, duration: str,
                     mode: str, where: str, takeaway: str) -> List[Dict[str, Any]]:
    return [
        badge(filename),
        header(title, subtitle, duration, mode, where, takeaway),
        code(BOOTSTRAP),
        code(APIKEY),
    ]
