"""
validation.py — L6, Validation & Guardrails. The attending's sign-off.
======================================================================

WHY this file exists
--------------------
Here is the sentence that justifies this entire layer:

    **A model's output is a proposal. Only your system can turn it into a
    decision.**

In the ER, the resident forms an opinion and the attending signs it. Not
because the resident is careless, but because a signature is an institution
accepting liability, and an institution cannot accept liability for something
it did not check.

Skip this layer and you have built a system whose worst-case behaviour is
whatever the model's worst-case behaviour is. Ship that into claims handling
and the model's bad day becomes a regulatory finding.

THE TWO HALVES
--------------
**Contract validation** asks: *is this the right shape?* Valid JSON, required
fields, enums in range, numbers that are numbers. Cheap, total, and it catches
the failure mode that breaks production most often — not a wrong answer, a
*malformed* one that explodes three services downstream.

**Guardrails** ask: *is this allowed?* The shape can be perfect and the content
still unacceptable: an approval above the ceiling, a decision on a lapsed
policy, a settlement figure stated as guaranteed, a claim about cover with no
citation behind it.

WHY GUARDRAILS ARE CODE AND NOT PROMPT
--------------------------------------
Every rule below is *also* stated in the T1 tier of `prompts.py`. That is not
duplication — it is defence in depth, and the division of labour is exact:

    the prompt makes the right behaviour LIKELY.
    the guardrail makes the wrong behaviour IMPOSSIBLE.

Probability is not a control. When a regulator asks how you prevent approvals
above ₹50,000, "we asked the model nicely and it usually complies" is not an
answer. `guard_approval_ceiling` is.

WHAT THIS LAYER DOES *NOT* DO
-----------------------------
It does not fix the output. A guardrail that silently rewrites a decision
destroys the audit trail and teaches the team nothing. It downgrades,
annotates, and records — and the trace shows exactly which rule fired.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import data as records

# The auto-approval ceiling, in rupees. Mirrors prompts.Tier.ORGANIZATIONAL.
# One constant, imported by both the guardrail and the tests, so the two can
# never drift apart — a small thing that prevents a very annoying incident.
AUTO_APPROVAL_CEILING_INR = 50_000

VALID_RECOMMENDATIONS = ("APPROVE", "REFER", "DECLINE")
VALID_CONFIDENCE = ("HIGH", "MEDIUM", "LOW")


class Severity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    BLOCK = "BLOCK"   # the decision may not stand as written


@dataclass
class Violation:
    rule: str
    severity: Severity
    message: str
    remedy: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"[{self.severity.value}] {self.rule}: {self.message}"


@dataclass
class ClaimDecision:
    """The output contract. The *only* shape allowed to leave the system.

    Written by hand rather than with pydantic on purpose: in a 120-minute
    session the learner should see that a contract is just fields, types and
    rules, with no framework required. `from_model_output` is where a string
    becomes a typed object, and that transition is the layer boundary.
    """

    claim_id: str
    recommendation: str
    rationale: str
    policy_status_cited: str = ""
    assessed_amount: Optional[float] = None
    confidence: str = "LOW"
    missing_evidence: List[str] = field(default_factory=list)
    conflicts_detected: List[str] = field(default_factory=list)
    injection_attempt: bool = False
    citations: List[str] = field(default_factory=list)

    # Filled by the guardrail chain; never by the model.
    violations: List[Violation] = field(default_factory=list)
    downgraded_from: Optional[str] = None

    @property
    def blocked(self) -> bool:
        return any(v.severity is Severity.BLOCK for v in self.violations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "policy_status_cited": self.policy_status_cited,
            "assessed_amount": self.assessed_amount,
            "confidence": self.confidence,
            "missing_evidence": self.missing_evidence,
            "conflicts_detected": self.conflicts_detected,
            "injection_attempt": self.injection_attempt,
            "citations": self.citations,
            "downgraded_from": self.downgraded_from,
            "violations": [str(v) for v in self.violations],
        }

    def render(self) -> str:  # pragma: no cover - display only
        head = f"{self.claim_id}  ->  {self.recommendation}"
        if self.downgraded_from:
            head += f"   (downgraded from {self.downgraded_from})"
        lines = [head, f"confidence: {self.confidence}", "", self.rationale, ""]
        if self.assessed_amount is not None:
            lines.append(f"assessed amount: Rs {self.assessed_amount:,.0f}")
        if self.injection_attempt:
            lines.append("!! injection attempt detected in claimant content")
        for label, items in (("conflicts", self.conflicts_detected),
                             ("missing evidence", self.missing_evidence),
                             ("citations", self.citations)):
            if items:
                lines.append(f"{label}: " + "; ".join(map(str, items)))
        if self.violations:
            lines.append("")
            lines.append("guardrails fired:")
            lines.extend(f"  {v}" for v in self.violations)
        return "\n".join(lines)


class ContractError(ValueError):
    """Raised when the model's output is not the agreed shape."""


def extract_json(text: str) -> Dict[str, Any]:
    """Get a JSON object out of whatever the model actually sent.

    Models wrap JSON in markdown fences, prepend "Here is the assessment:", and
    occasionally emit two objects. This function is unglamorous and it is
    exactly the kind of code every real GenAI system has. Writing it once, in
    the validation layer, beats writing it five times in five services.
    """
    text = (text or "").strip()
    if not text:
        raise ContractError("model returned empty output")

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start, depth = text.find("{"), 0
    if start == -1:
        raise ContractError(f"no JSON object found in output: {text[:200]!r}")
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as exc:
                    raise ContractError(f"malformed JSON object: {exc}") from exc
    raise ContractError("unterminated JSON object in model output")


def validate_contract(payload: Dict[str, Any], claim_id: str) -> ClaimDecision:
    """Shape check. Strict, because permissive parsing hides defects."""
    missing = [f for f in ("recommendation", "rationale") if not payload.get(f)]
    if missing:
        raise ContractError(f"missing required field(s): {missing}")

    rec = str(payload["recommendation"]).strip().upper()
    if rec not in VALID_RECOMMENDATIONS:
        raise ContractError(
            f"recommendation {rec!r} not in {VALID_RECOMMENDATIONS}"
        )

    conf = str(payload.get("confidence", "LOW")).strip().upper()
    if conf not in VALID_CONFIDENCE:
        conf = "LOW"  # an unparseable confidence is not a high one

    amount = payload.get("assessed_amount")
    if amount is not None:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise ContractError(f"assessed_amount is not a number: {amount!r}")

    def as_list(key: str) -> List[str]:
        v = payload.get(key) or []
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v]

    return ClaimDecision(
        claim_id=str(payload.get("claim_id") or claim_id),
        recommendation=rec,
        rationale=str(payload["rationale"]).strip(),
        policy_status_cited=str(payload.get("policy_status_cited", "")),
        assessed_amount=amount,
        confidence=conf,
        missing_evidence=as_list("missing_evidence"),
        conflicts_detected=as_list("conflicts_detected"),
        injection_attempt=bool(payload.get("injection_attempt", False)),
        citations=as_list("citations"),
    )


# ---------------------------------------------------------------------------
# The guardrail chain. Each guard is a pure function:
#     (decision, context) -> list[Violation]
# and may mutate `decision.recommendation` ONLY by downgrading, recording the
# original in `downgraded_from`. Nothing here ever upgrades a decision — a
# guardrail that can approve is not a guardrail.
# ---------------------------------------------------------------------------

Guard = Callable[[ClaimDecision, Dict[str, Any]], List[Violation]]


def _downgrade(decision: ClaimDecision, to: str) -> None:
    order = {"APPROVE": 0, "REFER": 1, "DECLINE": 2}
    if order[to] > order[decision.recommendation]:
        if decision.downgraded_from is None:
            decision.downgraded_from = decision.recommendation
        decision.recommendation = to


def guard_policy_status(decision: ClaimDecision, ctx: Dict[str, Any]) -> List[Violation]:
    """CP-03: no decision other than DECLINE on a non-ACTIVE policy.

    The model is *told* this in T1. This guard is what makes it true.
    """
    policy = ctx.get("policy")
    if not policy:
        return [Violation("policy_status", Severity.WARN,
                          "no policy record in context; cannot verify status")]
    if policy.status != "ACTIVE" and decision.recommendation != "DECLINE":
        _downgrade(decision, "DECLINE")
        return [Violation(
            "CP-03 policy_status", Severity.BLOCK,
            f"policy {policy.policy_id} is {policy.status}; only DECLINE is permitted",
            remedy="downgraded to DECLINE",
        )]
    return []


def guard_approval_ceiling(decision: ClaimDecision, ctx: Dict[str, Any]) -> List[Violation]:
    """CP-07: the ₹50,000 auto-approval ceiling, as code rather than hope."""
    if decision.recommendation != "APPROVE":
        return []
    amount = decision.assessed_amount
    if amount is None:
        amount = float(ctx.get("claimed_amount") or 0)
    if amount > AUTO_APPROVAL_CEILING_INR:
        _downgrade(decision, "REFER")
        return [Violation(
            "CP-07 approval_ceiling", Severity.BLOCK,
            f"APPROVE at Rs {amount:,.0f} exceeds the Rs {AUTO_APPROVAL_CEILING_INR:,} ceiling",
            remedy="downgraded to REFER",
        )]
    return []


def guard_fraud_band(decision: ClaimDecision, ctx: Dict[str, Any]) -> List[Violation]:
    """FC-11: a HIGH band cannot be argued away by a persuasive claimant."""
    fraud = ctx.get("fraud") or {}
    if fraud.get("band") == "HIGH" and decision.recommendation == "APPROVE":
        _downgrade(decision, "REFER")
        return [Violation(
            "FC-11 fraud_band", Severity.BLOCK,
            f"fraud band HIGH (score {fraud.get('score')}) forbids APPROVE",
            remedy="downgraded to REFER",
        )]
    return []


_GUARANTEE_PATTERNS = [
    r"\bguarantee(d|s)?\b",
    r"\bwill (?:definitely |certainly )?be (?:paid|settled|approved|credited)\b",
    r"\bfinal settlement\b",
    r"\bassured\b",
    r"\byou will receive\b",
]


def guard_no_guarantee(decision: ClaimDecision, ctx: Dict[str, Any]) -> List[Violation]:
    """T0 regulatory: never imply a guaranteed settlement.

    A regex here is defensible in a way it is *not* defensible for injection
    defence — the prohibited phrasings are a small closed set defined by the
    regulator, not an open-ended adversary trying to evade you.
    """
    out = []
    for pat in _GUARANTEE_PATTERNS:
        if re.search(pat, decision.rationale, re.IGNORECASE):
            out.append(Violation(
                "T0 no_guarantee", Severity.BLOCK,
                f"rationale implies a guaranteed settlement (matched /{pat}/)",
                remedy="rationale must be regenerated before release",
            ))
            break
    return out


def guard_citation_required(decision: ClaimDecision, ctx: Dict[str, Any]) -> List[Violation]:
    """AIG-02: an uncited claim about cover is treated as a hallucination.

    This is the cheapest hallucination control most teams never build: don't
    ask 'is this true?', ask 'did it come from somewhere?'
    """
    if decision.recommendation == "REFER" and not decision.citations:
        return [Violation("AIG-02 citation", Severity.WARN,
                          "no tool citations recorded")]
    if not decision.citations:
        return [Violation(
            "AIG-02 citation", Severity.BLOCK,
            "decision cites no tool results; every cover assertion must be traceable",
            remedy="re-run with tool use before releasing",
        )]
    if decision.policy_status_cited and "lookup_policy" not in decision.citations:
        return [Violation("AIG-02 citation", Severity.WARN,
                          "policy status asserted without citing lookup_policy")]
    return []


def guard_injection_reported(decision: ClaimDecision, ctx: Dict[str, Any]) -> List[Violation]:
    """If the claim is known to carry an injection, the system must have noticed.

    In a classroom this is a scored check. In production the equivalent is a
    canary: inject a known-benign attack periodically and alert when the
    detection rate drops, because that is how you learn a prompt change broke
    your defences *before* a real attacker does.
    """
    if ctx.get("expect_injection") and not decision.injection_attempt:
        return [Violation(
            "injection_detection", Severity.WARN,
            "known injection in claimant content was not reported by the model",
            remedy="the guardrails still held; the detection signal did not",
        )]
    return []


DEFAULT_GUARDS: Tuple[Guard, ...] = (
    guard_policy_status,
    guard_approval_ceiling,
    guard_fraud_band,
    guard_no_guarantee,
    guard_citation_required,
    guard_injection_reported,
)


def apply_guardrails(
    decision: ClaimDecision,
    context: Dict[str, Any],
    guards: Tuple[Guard, ...] = DEFAULT_GUARDS,
) -> ClaimDecision:
    """Run the chain. Order matters: status before ceiling before fraud.

    Every guard runs even after one blocks — you want the *complete* list of
    what was wrong, not the first thing that was wrong. Stopping early is how
    teams fix one violation, redeploy, and discover the second one in prod.
    """
    for guard in guards:
        decision.violations.extend(guard(decision, context))
    return decision


def build_context(claim_id: str) -> Dict[str, Any]:
    """Assemble the verified facts the guardrails check against.

    Note that this reads the systems of record DIRECTLY rather than trusting
    anything the model reported. A guardrail that validates the model's output
    using the model's own claims is not a guardrail; it is a mirror.
    """
    claim = records.get_claim(claim_id)
    policy = records.get_policy(claim.policy_id) if claim else None
    return {
        "claim": claim,
        "policy": policy,
        "fraud": records.get_fraud(claim_id) or {},
        "claimed_amount": claim.claimed_amount if claim else None,
        "expect_injection": claim_id.upper() == "CLM-4418",
    }
