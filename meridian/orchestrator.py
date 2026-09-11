"""
orchestrator.py — L2. The triage nurse, and the only place control flow lives.
==============================================================================

WHY this file exists
--------------------
The agenda asks a specific question: *why do GenAI systems need orchestration
beyond traditional ML pipelines?* Here is the answer, in one contrast.

A traditional ML pipeline:

    features -> model.predict() -> post-process -> done

The shape is fixed. You wrote it. It executes the same way every time, and its
latency and cost are known before it runs.

A GenAI system:

    prompt -> model -> "I want to call lookup_policy"
                    -> run it -> feed it back
                    -> model -> "now compute_payout"
                    -> run it -> feed it back
                    -> model -> an answer
                    -> validate -> maybe reject -> maybe retry

**The number of steps is decided at runtime, by a probabilistic component.**
That single sentence is the whole architectural shift. It means:

    - you cannot precompute cost or latency, so you need BUDGETS
    - the model may never stop, so something else must own TERMINATION
    - any step may fail, so you need RETRIES that do not loop forever
    - the output is a proposal, so VALIDATION is a pipeline stage, not a test

Every one of those is orchestration's job, and none of them is the model's.
The moment you let the model decide when it is finished, you have handed your
system's termination condition to a component that does not know your budget.

THE ANALOGY
-----------
The triage nurse does not diagnose. The nurse decides who is seen, in what
order, how long they wait, and when to escalate — and crucially, the nurse
decides when a case has consumed enough of the department's capacity. A
hospital where the doctor decides how long to keep seeing the same patient is
a hospital with a waiting room full of people who will not be seen today.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import data as records
from .config import Completion, LLM, get_llm
from .observability import Trace
from .prompts import PromptHierarchy
from .tools import ToolRegistry, default_registry
from .validation import (
    ClaimDecision,
    ContractError,
    apply_guardrails,
    build_context,
    extract_json,
    validate_contract,
)


@dataclass
class Budget:
    """The limits orchestration enforces because nothing else will.

    These numbers are deliberately small. A budget you never hit is a budget
    you have not tested, and the first time you hit it should not be in
    production at month-end.
    """

    max_model_calls: int = 6
    max_tool_calls: int = 8
    max_tokens: int = 20_000
    max_repair_attempts: int = 1   # contract violations get ONE re-ask

    def exceeded(self, trace: Trace) -> Optional[str]:
        if trace.model_calls >= self.max_model_calls:
            return f"model call budget exhausted ({self.max_model_calls})"
        if len(trace.tool_calls) >= self.max_tool_calls:
            return f"tool call budget exhausted ({self.max_tool_calls})"
        if trace.total_tokens >= self.max_tokens:
            return f"token budget exhausted ({self.max_tokens})"
        return None


@dataclass
class TriageResult:
    """What the system returns. Decision AND trace, never one without the other."""

    decision: Optional[ClaimDecision]
    trace: Trace
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.decision is not None and self.error is None

    def render(self) -> str:  # pragma: no cover - display only
        parts = []
        if self.decision:
            parts.append(self.decision.render())
        if self.error:
            parts.append(f"\nORCHESTRATION ERROR: {self.error}")
        parts.append("\n" + self.trace.render())
        return "\n".join(parts)


class TriageOrchestrator:
    """The full system: L1 through L7, wired.

        orch = TriageOrchestrator()
        result = orch.run("CLM-4417")
        print(result.render())

    Read `run()` top to bottom and you have read the architecture. That is the
    point of keeping it in one readable method rather than spreading it across
    a framework: in a 120-minute session, the control flow must be visible.
    """

    def __init__(
        self,
        llm: Optional[LLM] = None,
        hierarchy: Optional[PromptHierarchy] = None,
        registry: Optional[ToolRegistry] = None,
        budget: Optional[Budget] = None,
        enforce_guardrails: bool = True,
    ) -> None:
        self.llm = llm or get_llm()
        self.hierarchy = hierarchy or PromptHierarchy.meridian_triage()
        self.registry = registry or default_registry()
        self.budget = budget or Budget()
        # Turning this off is notebook 06's demonstration of what L6 was doing.
        self.enforce_guardrails = enforce_guardrails

    # -- L1: intake ---------------------------------------------------------

    def _intake(self, claim_id: str, trace: Trace) -> Optional[records.Claim]:
        """L1. Validate the request before a single token is spent.

        Cheap checks at the door are the highest-leverage thing in the whole
        stack: they cost microseconds and prevent whole categories of expensive
        downstream confusion.
        """
        span = trace.span("intake", "L1", claim_id=claim_id)
        claim = records.get_claim(claim_id)
        if claim is None:
            span.error = f"unknown claim {claim_id}"
            span.finish(accepted=False)
            return None
        span.finish(
            accepted=True,
            claim_type=claim.claim_type,
            claimed_amount=claim.claimed_amount,
            statement_chars=len(claim.claimant_statement),
            documents=len(claim.documents),
        )
        return claim

    # -- L3: context assembly ----------------------------------------------

    def _assemble(self, claim: records.Claim, trace: Trace) -> List[Dict[str, Any]]:
        """L3. Build the chart.

        Note what goes where. The claim's *metadata* (id, type, amount) is
        trusted context — it came from our own intake system. The claimant's
        *statement* is untrusted, and goes behind the fence. Same claim, two
        different trust levels, and the split is the security control.
        """
        span = trace.span("assemble_prompt", "L3")
        messages = self.hierarchy.compile(
            trusted_context={
                "claim_id": claim.claim_id,
                "policy_id": claim.policy_id,
                "claim_type": claim.claim_type,
                "claimed_amount_inr": claim.claimed_amount,
                "incident_date": claim.incident_date,
                "reported_date": claim.reported_date,
                "documents_on_file": ", ".join(claim.documents) or "none",
            },
            untrusted={"Claimant statement": claim.claimant_statement},
            user_task=f"Assess claim {claim.claim_id} and return the JSON contract.",
        )
        span.finish(
            fingerprint=self.hierarchy.fingerprint,
            quarantine=self.hierarchy.quarantine_untrusted,
            system_chars=len(messages[0]["content"]),
            tiers={t.label: len(self.hierarchy.by_tier(t))
                   for t in sorted(set(d.tier for d in self.hierarchy.directives), reverse=True)},
        )
        return messages

    # -- L4 + L5: the reasoning loop ---------------------------------------

    def _reason(
        self, messages: List[Dict[str, Any]], trace: Trace
    ) -> Tuple[Optional[Completion], Optional[str]]:
        """Alternate model calls and tool calls until the model stops asking.

        THE LOOP IS ORCHESTRATION'S, NOT THE MODEL'S. The model signals intent
        by emitting tool calls; this function decides whether to honour them,
        how many times, and when to stop regardless of what the model wants.
        """
        tool_schemas = self.registry.schemas()

        while True:
            reason = self.budget.exceeded(trace)
            if reason:
                return None, reason

            span = trace.span("model_call", "L4", model=self.llm.model)
            completion = self.llm.complete(messages, tools=tool_schemas)
            span.finish(
                finish_reason=completion.finish_reason,
                wants_tools=completion.wants_tools,
                tool_names=[c.name for c in completion.tool_calls],
                total_tokens=completion.total_tokens,
                cost_usd=completion.cost_usd,
                latency_ms=completion.latency_ms,
            )

            if not completion.wants_tools:
                return completion, None

            # Echo the model's own tool-call message back before the results —
            # the API requires the pairing, and more importantly the model
            # needs to see what it asked for.
            messages.append({
                "role": "assistant",
                "content": completion.text or None,
                "tool_calls": [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                    for c in completion.tool_calls
                ],
            })

            for call in completion.tool_calls:
                tspan = trace.span("tool_call", "L5", tool=call.name, arguments=call.arguments)
                result = self.registry.run(call.name, call.arguments)
                tspan.finish(ok=result.ok, error=result.error,
                             result_preview=str(result.data)[:160] if result.ok else None)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result.to_model_string(),
                })

    # -- L6: contract + guardrails -----------------------------------------

    def _validate(
        self,
        completion: Completion,
        claim: records.Claim,
        messages: List[Dict[str, Any]],
        trace: Trace,
    ) -> Optional[ClaimDecision]:
        """Parse, and if the shape is wrong, re-ask ONCE with the error.

        Re-asking with the specific parse error is far more effective than
        retrying blind: you are giving the model the one piece of information
        it lacked. But it is bounded at one attempt, because a model that
        cannot produce your contract twice is not going to on the fifth try —
        it is telling you the contract is unclear.
        """
        attempts = 0
        current = completion

        while True:
            span = trace.span("contract_validation", "L6")
            try:
                payload = extract_json(current.text)
                decision = validate_contract(payload, claim.claim_id)
                span.finish(ok=True, recommendation=decision.recommendation,
                            confidence=decision.confidence)
                break
            except ContractError as exc:
                span.error = str(exc)
                span.finish(ok=False, attempt=attempts + 1)
                attempts += 1
                if attempts > self.budget.max_repair_attempts:
                    return None
                messages.append({"role": "assistant", "content": current.text})
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your previous output failed contract validation: {exc}\n"
                        "Return ONLY the JSON object specified in the output contract, "
                        "with no prose and no markdown fences."
                    ),
                })
                rspan = trace.span("model_call", "L4", model=self.llm.model, purpose="contract_repair")
                current = self.llm.complete(messages)
                rspan.finish(total_tokens=current.total_tokens, cost_usd=current.cost_usd,
                             latency_ms=current.latency_ms)

        if not self.enforce_guardrails:
            trace.record("guardrails", "L6", enforced=False,
                         note="DISABLED — notebook 06 only; this is what L6 was doing")
            return decision

        gspan = trace.span("guardrails", "L6")
        context = build_context(claim.claim_id)
        decision = apply_guardrails(decision, context)
        gspan.finish(
            enforced=True,
            violations=[str(v) for v in decision.violations],
            blocked=decision.blocked,
            downgraded_from=decision.downgraded_from,
            final=decision.recommendation,
        )
        return decision

    # -- the whole system ---------------------------------------------------

    def run(self, claim_id: str, session_directives: Optional[List[str]] = None) -> TriageResult:
        """One claim, end to end. L1 -> L2 -> L3 -> L4/L5 -> L6 -> L7."""
        trace = Trace(claim_id=claim_id, model=self.llm.model,
                      prompt_fingerprint=self.hierarchy.fingerprint)

        if session_directives:
            # T3 is the ONLY tier a runtime caller may write to. Everything
            # above it requires a release with an approver.
            for directive in session_directives:
                self.hierarchy.add_session(directive)
            trace.prompt_fingerprint = self.hierarchy.fingerprint

        claim = self._intake(claim_id, trace)
        if claim is None:
            return TriageResult(None, trace, error=f"unknown claim {claim_id}")

        messages = self._assemble(claim, trace)
        completion, budget_error = self._reason(messages, trace)
        if completion is None:
            return TriageResult(None, trace, error=budget_error)

        decision = self._validate(completion, claim, messages, trace)
        if decision is None:
            return TriageResult(None, trace,
                                error="model could not produce a valid contract")

        trace.record("audit_record", "L7", **trace.to_audit_record())
        return TriageResult(decision, trace)
