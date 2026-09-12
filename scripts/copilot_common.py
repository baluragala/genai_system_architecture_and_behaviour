"""Shared cells and helpers for the Zero-to-Hero Enterprise Copilot notebook.

This notebook is deliberately **standalone** — it does not import `meridian`.
A "zero to hero" artifact that requires another package to run is not zero to
hero. Everything it needs is defined in its own cells, which is also why it can
be handed to someone who has never seen this repo.

Its spine analogy is **aviation**, kept distinct from the session notebooks'
hospital ER so the two can be taught in the same week without colliding.

    python scripts/build_copilot.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nbtools import ROOT, code, md, notebook  # noqa: F401

FILE = "GenAI_System_Architecture_Zero_to_Hero_Enterprise_Copilot.ipynb"
OUT = os.path.join(ROOT, FILE)

MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"


def h1(text: str) -> "dict":
    return md(text)


def why(text: str) -> "dict":
    """The WHY block: a concrete failure this component prevents."""
    return md("## WHY\n\n" + text)


def what(text: str) -> "dict":
    return md("## WHAT\n\n" + text)


def how(text: str) -> "dict":
    return md("## HOW\n\n" + text)


def predict(question: str) -> "dict":
    return md(
        "> ### ✋ Predict before you run\n"
        f"> {question}\n>\n"
        "> Write your answer down first. Being wrong out loud is the lesson."
    )


def breaks(text: str) -> "dict":
    """The question asked after every HOW block, all notebook long."""
    return md(
        "> ### 🔧 What does this look like when it goes wrong?\n> " + text
    )


def analogy(text: str) -> "dict":
    return md("> ### ✈️ The analogy\n> " + text)


# ---------------------------------------------------------------------------
# Shared cells
# ---------------------------------------------------------------------------

INSTALL = '''
# ============================================================
# SETUP 1 of 2 — dependencies. Run this first.
# ============================================================
# Installs only what is MISSING. Checking by import is the only reliable test:
# "am I in Colab?" tells you nothing about what is already installed there.
import importlib.util, subprocess, sys

REQUIRED = {                      # import name -> pip package
    "openai":  "openai>=1.30",
    "numpy":   "numpy",
    "pandas":  "pandas",
    "sklearn": "scikit-learn",
    "pydantic":"pydantic>=2.7",
    "PIL":     "pillow",
    "mcp":     "mcp>=2,<3",       # section 24 runs a real MCP server
}

def _present(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False

missing = sorted({pkg for mod, pkg in REQUIRED.items() if not _present(mod)})
if missing:
    print("installing:", ", ".join(missing))
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *missing], check=False)
else:
    print("dependencies: all present")

IN_COLAB = "google.colab" in sys.modules
print("colab:", IN_COLAB, "| python:", sys.version.split()[0])
'''

APIKEY = '''
# ============================================================
# SETUP 2 of 2 — your OpenAI API key.
# ============================================================
#   Colab : sidebar -> key icon -> add a secret named OPENAI_API_KEY
#           -> toggle "Notebook access" ON -> re-run this cell
#   local : export OPENAI_API_KEY=sk-...   then restart the kernel
#
# This notebook calls a real model. Every "optional" section in the original
# version of this notebook has been made real, which means they all cost money
# -- about 3 to 8 US cents for a full top-to-bottom run at gpt-4o-mini prices.
import os

def load_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    try:                                          # Colab Secrets
        from google.colab import userdata
        key = userdata.get("OPENAI_API_KEY")
        if key:
            os.environ["OPENAI_API_KEY"] = key
            return key
    except Exception:
        pass
    raise RuntimeError(
        "OPENAI_API_KEY is not set.\\n"
        "  Colab : sidebar -> key icon -> add OPENAI_API_KEY -> Notebook access ON\\n"
        "  local : export OPENAI_API_KEY=sk-...  then restart the kernel"
    )

load_api_key()

from openai import OpenAI

client = OpenAI()
CHAT_MODEL  = "gpt-4o-mini"        # chat + vision, cheap enough to run in class
EMBED_MODEL = "text-embedding-3-small"

print("OpenAI client ready")
print("  chat model      :", CHAT_MODEL)
print("  embedding model :", EMBED_MODEL)
'''

IMPORTS = '''
# ============================================================
# Standard imports used throughout the notebook.
# ============================================================
import base64, json, math, re, sqlite3, textwrap, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

pd.set_option("display.max_colwidth", 80)
print("imports ready")
'''


def save(cells) -> str:
    import json as _json

    with open(OUT, "w", encoding="utf-8") as fh:
        _json.dump(notebook(cells), fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return OUT
