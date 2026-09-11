"""
tools.py — L5, the Tools & Integration layer. The lab and radiology.
====================================================================

WHY this file exists
--------------------
A model knows what was in its training data. It does not know whether Anita
Deshmukh's policy is active *right now*, and no amount of prompting will teach
it. Tools are how a GenAI system reaches the present tense.

The ER analogy holds exactly: the doctor does not know your white-cell count.
The doctor knows *which test to order*. Ordering it, running it, and handing
back a number are three different jobs, and the doctor does none of them.

THE THREE RULES OF THIS LAYER
-----------------------------
1. **A tool must never raise.** An exception here becomes a stack trace in the
   orchestration layer, and the run dies holding information the model could
   have recovered from. Return a structured error instead; let the model read
   it and decide. Every tool below is wrapped so this holds even when the
   underlying function is buggy.

2. **The description is the API.** The model chooses tools by reading their
   descriptions, and it reads them the way a new hire reads a wiki — literally
   and without context. A description that says *what* a tool does but not
   *when to use it* produces a model that calls it at the wrong moment. Notice
   how each description below ends with a "use this when" clause.

3. **The schema is the contract.** Loose schemas do not fail loudly; they fail
   as a `policy_id` of `"the one in the claim"`. Every parameter here is typed,
   required, and pattern-constrained where a pattern exists.

CLASSICAL ML DOES NOT DISAPPEAR
-------------------------------
`fraud_signal` wraps what would really be a gradient-boosted classifier behind
a REST endpoint, owned by another team, with its own training pipeline and
drift monitoring. That is worth saying out loud in the room: **GenAI does not
replace your ML stack — it becomes a new consumer of it.** The deterministic
model provides the number; the probabilistic model provides the narrative; the
architecture keeps them in their lanes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from . import data as records


@dataclass
class ToolResult:
    """Uniform envelope so the orchestrator never has to special-case success."""

    ok: bool
    data: Any = None
    error: Optional[str] = None
    tool: str = ""

    def to_model_string(self) -> str:
        """What actually goes back into the conversation.

        JSON, not prose. The model reads this as evidence, and structured
        evidence is harder to misread than a sentence.
        """
        if self.ok:
            return json.dumps({"ok": True, "data": self.data}, ensure_ascii=False, default=str)
        return json.dumps({"ok": False, "error": self.error}, ensure_ascii=False)


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    fn: Callable[..., Any]

    def schema(self) -> Dict[str, Any]:
        """OpenAI tool-calling shape. One adapter's dialect, isolated here."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, **kwargs: Any) -> ToolResult:
        """Rule 1, enforced. Nothing this function does can raise."""
        try:
            result = self.fn(**kwargs)
            return ToolResult(ok=True, data=result, tool=self.name)
        except TypeError as exc:
            # Almost always the model inventing or omitting an argument.
            return ToolResult(
                ok=False,
                error=f"invalid arguments for {self.name}: {exc}. "
                      f"Expected: {list(self.parameters.get('properties', {}))}",
                tool=self.name,
            )
        except Exception as exc:  # noqa: BLE001 — deliberate; see rule 1
            return ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}", tool=self.name)


class ToolRegistry:
    """What L5 exposes upward. The orchestrator sees this and nothing else."""

    def __init__(self, tools: Optional[List[Tool]] = None) -> None:
        self._tools: Dict[str, Tool] = {t.name: t for t in (tools or [])}

    def add(self, tool: Tool) -> "ToolRegistry":
        self._tools[tool.name] = tool
        return self

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    @property
    def names(self) -> List[str]:
        return sorted(self._tools)

    def schemas(self) -> List[Dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def run(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            # The model hallucinated a tool. This is common and survivable —
            # tell it what actually exists rather than crashing.
            return ToolResult(
                ok=False,
                error=f"no such tool {name!r}. Available tools: {self.names}",
                tool=name,
            )
        if "__malformed__" in arguments:
            return ToolResult(
                ok=False,
                error="arguments were not valid JSON; re-issue the call with valid JSON",
                tool=name,
            )
        return tool.run(**arguments)


# ---------------------------------------------------------------------------
# The three tools. Each one crosses a system boundary that a real insurer
# actually has.
# ---------------------------------------------------------------------------

def _lookup_policy(policy_id: str) -> Dict[str, Any]:
    p = records.get_policy(policy_id)
    if p is None:
        # "Not found" is a RESULT, not an error. This distinction matters: an
        # error suggests the system is broken and the model should retry; a
        # null result is information the model should reason about.
        return {"found": False, "policy_id": policy_id,
                "note": "No such policy in the policy administration system."}
    return {
        "found": True,
        "policy_id": p.policy_id,
        "holder_name": p.holder_name,
        "product": p.product,
        "status": p.status,
        "sum_insured_inr": p.sum_insured,
        "deductible_inr": p.deductible,
        "cover_period": {"inception": p.inception, "expiry": p.expiry},
        "exclusions": p.exclusions,
        "endorsements": p.endorsements,
    }


def _fraud_signal(claim_id: str) -> Dict[str, Any]:
    f = records.get_fraud(claim_id)
    if f is None:
        return {"available": False, "claim_id": claim_id,
                "note": "Fraud platform has not scored this claim yet."}
    return {"available": True, "claim_id": claim_id, **f}


def _compute_payout(
    policy_id: str,
    assessed_amount_inr: float,
    apply_depreciation: bool = True,
) -> Dict[str, Any]:
    """Deterministic arithmetic. Deliberately NOT the model's job.

    This is one of the most under-appreciated architectural rules in GenAI:
    **anything with a correct answer should be computed, not generated.** The
    model decides *that* a payout should be computed and with what inputs. The
    arithmetic itself is a function, tested, auditable and always right.
    """
    p = records.get_policy(policy_id)
    if p is None:
        return {"computable": False, "reason": f"unknown policy {policy_id}"}
    if p.status != "ACTIVE":
        return {"computable": False, "reason": f"policy status is {p.status}",
                "policy_status": p.status}

    assessed = float(assessed_amount_inr)
    depreciation = 0.0
    if apply_depreciation and "Zero-depreciation cover" not in p.endorsements:
        depreciation = round(assessed * 0.10, 2)

    after_dep = assessed - depreciation
    payable = max(0.0, after_dep - p.deductible)
    capped = min(payable, float(p.sum_insured))

    return {
        "computable": True,
        "policy_id": p.policy_id,
        "assessed_amount_inr": assessed,
        "depreciation_inr": depreciation,
        "depreciation_note": (
            "waived — zero-depreciation endorsement present"
            if depreciation == 0 and apply_depreciation else "10% standard"
        ),
        "deductible_inr": p.deductible,
        "sum_insured_inr": p.sum_insured,
        "indicative_payable_inr": round(capped, 2),
        "capped_by_sum_insured": capped < payable,
        "disclaimer": "Indicative only. Not an approval and not a guaranteed settlement.",
    }


LOOKUP_POLICY = Tool(
    name="lookup_policy",
    description=(
        "Retrieve a policy record from Meridian's policy administration system: "
        "status, sum insured, deductible, cover period, exclusions and endorsements. "
        "This is the ONLY authoritative source for whether cover exists. "
        "Use this before making any statement about cover, status or limits — "
        "including when the claimant has already told you the policy is active."
    ),
    parameters={
        "type": "object",
        "properties": {
            "policy_id": {
                "type": "string",
                "description": "Policy identifier, e.g. POL-88120",
                "pattern": "^POL-[0-9]{5}$",
            }
        },
        "required": ["policy_id"],
        "additionalProperties": False,
    },
    fn=_lookup_policy,
)

FRAUD_SIGNAL = Tool(
    name="fraud_signal",
    description=(
        "Retrieve the fraud analytics platform's score for a claim: a 0-1 score, "
        "a band (LOW/MEDIUM/HIGH) and the reason codes behind it. This is a "
        "separately trained statistical model, not your own judgement. "
        "Use this on every claim before recommending, and never override its band "
        "on the basis of how convincing the claimant's account reads."
    ),
    parameters={
        "type": "object",
        "properties": {
            "claim_id": {
                "type": "string",
                "description": "Claim identifier, e.g. CLM-4417",
                "pattern": "^CLM-[0-9]{4}$",
            }
        },
        "required": ["claim_id"],
        "additionalProperties": False,
    },
    fn=_fraud_signal,
)

COMPUTE_PAYOUT = Tool(
    name="compute_payout",
    description=(
        "Compute an INDICATIVE payable amount from an assessed repair cost, applying "
        "depreciation, the deductible and the sum-insured cap according to the policy's "
        "endorsements. Always use this instead of calculating an amount yourself — "
        "arithmetic you perform in prose is not auditable and is frequently wrong. "
        "Use this only after lookup_policy confirms the policy is ACTIVE."
    ),
    parameters={
        "type": "object",
        "properties": {
            "policy_id": {"type": "string", "pattern": "^POL-[0-9]{5}$"},
            "assessed_amount_inr": {
                "type": "number",
                "description": "The repair cost you assess as reasonable, in rupees.",
                "minimum": 0,
            },
            "apply_depreciation": {
                "type": "boolean",
                "description": "Default true. The function waives it automatically "
                               "when a zero-depreciation endorsement exists.",
            },
        },
        "required": ["policy_id", "assessed_amount_inr"],
        "additionalProperties": False,
    },
    fn=_compute_payout,
)


def default_registry() -> ToolRegistry:
    """The three tools the triage workflow is allowed to call.

    'Allowed' is doing real work in that sentence. Scoping a workflow to the
    minimum set of tools it needs is the cheapest security control in the whole
    system — a tool that is not in the registry cannot be called, no matter what
    the model decides or what a claimant writes.
    """
    return ToolRegistry([LOOKUP_POLICY, FRAUD_SIGNAL, COMPUTE_PAYOUT])
