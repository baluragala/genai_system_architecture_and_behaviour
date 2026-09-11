"""Shared fixtures.

THE STUBBING RULE FOR THIS PACKAGE
---------------------------------
The **tests** stub the model. The **notebooks never do.**

That split is deliberate and worth stating, because it looks inconsistent from
the outside. A test needs a deterministic, free, offline model so it can assert
things and run in CI. A notebook needs a real one, because the entire subject of
the session is how a *probabilistic* component behaves inside a system — and a
stub would answer identically every time and teach a comfortable lie.

The stub replaces `LLM` at exactly one seam: `complete()`. Everything else in
the package — prompt assembly, the tool loop, contract parsing, guardrails, the
trace — is the real code path.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meridian.config import Completion, ToolCall  # noqa: E402


class ScriptedLLM:
    """A model that replays a scripted sequence of turns.

    Each entry is either:
        {"tools": [(name, args), ...]}   -> emit tool calls
        {"text": "..."}                  -> emit a final answer
    """

    def __init__(self, script: List[Dict[str, Any]], model: str = "stub-model") -> None:
        self.script = list(script)
        self.model = model
        self.temperature = 0.0
        self.seed = None
        self.calls: List[List[Dict[str, Any]]] = []

    @property
    def name(self) -> str:
        return f"stub:{self.model}"

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 1200,
    ) -> Completion:
        self.calls.append(messages)
        if not self.script:
            raise AssertionError("ScriptedLLM ran out of script — the system "
                                 "made more model calls than the test expected")
        turn = self.script.pop(0)

        if "tools" in turn:
            return Completion(
                text="",
                tool_calls=[
                    ToolCall(id=f"call_{i}", name=n, arguments=a)
                    for i, (n, a) in enumerate(turn["tools"])
                ],
                finish_reason="tool_calls",
                model=self.model,
                prompt_tokens=100,
                completion_tokens=20,
            )
        return Completion(
            text=turn["text"],
            finish_reason="stop",
            model=self.model,
            prompt_tokens=120,
            completion_tokens=60,
        )


def decision_json(**overrides: Any) -> str:
    """A valid ClaimDecision payload, with fields overridable per test."""
    payload = {
        "claim_id": "CLM-4417",
        "recommendation": "APPROVE",
        "rationale": "Policy is active and the claimed amount is within limits.",
        "policy_status_cited": "ACTIVE",
        "assessed_amount": 38500,
        "confidence": "HIGH",
        "missing_evidence": [],
        "conflicts_detected": [],
        "injection_attempt": False,
        "citations": ["lookup_policy", "fraud_signal"],
    }
    payload.update(overrides)
    return json.dumps(payload)


@pytest.fixture
def scripted():
    return ScriptedLLM
