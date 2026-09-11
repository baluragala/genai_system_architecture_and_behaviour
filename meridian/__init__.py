"""
meridian — a GenAI claims-triage system, built one layer at a time.
===================================================================

The teaching package for **GenAI System Architecture & Behaviour** (C8W1S1).

    The model is the doctor. Your system is the hospital.

Seven layers, each a real object with a real boundary:

    L1  Experience / Interface      reception desk
    L2  Orchestration               triage nurse        orchestrator.py
    L3  Context & Prompt            the chart           prompts.py
    L4  Model                       the doctor          config.py
    L5  Tools & Integration         lab & radiology     tools.py / mcp_*.py
    L6  Validation & Guardrails     attending's sign-off validation.py
    L7  Observability & Governance  medical record      observability.py

Quick start (requires OPENAI_API_KEY):

    from meridian import TriageOrchestrator
    result = TriageOrchestrator().run("CLM-4417")
    print(result.render())
"""
from __future__ import annotations

__version__ = "1.0.0"

from .config import LLM, Completion, MissingAPIKey, current_config, get_llm
from .layers import BY_ID, STACK, LayerSpec, describe_stack, layer_quiz
from .observability import Span, Trace, compare
from .orchestrator import Budget, TriageOrchestrator, TriageResult
from .prompts import SCAFFOLDS, Directive, PromptHierarchy, Tier, with_scaffold
from .tools import Tool, ToolRegistry, ToolResult, default_registry
from .validation import (
    AUTO_APPROVAL_CEILING_INR,
    ClaimDecision,
    ContractError,
    Severity,
    Violation,
    apply_guardrails,
    build_context,
    extract_json,
    validate_contract,
)

__all__ = [
    "__version__",
    # L4
    "LLM", "Completion", "MissingAPIKey", "current_config", "get_llm",
    # the stack itself
    "STACK", "BY_ID", "LayerSpec", "describe_stack", "layer_quiz",
    # L2
    "TriageOrchestrator", "TriageResult", "Budget",
    # L3
    "PromptHierarchy", "Tier", "Directive", "SCAFFOLDS", "with_scaffold",
    # L5
    "Tool", "ToolRegistry", "ToolResult", "default_registry",
    # L6
    "ClaimDecision", "ContractError", "Severity", "Violation",
    "validate_contract", "apply_guardrails", "extract_json", "build_context",
    "AUTO_APPROVAL_CEILING_INR",
    # L7
    "Trace", "Span", "compare",
]
