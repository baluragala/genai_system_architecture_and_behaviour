"""Notebook 06 — Capstone: the whole stack, then diagram your own."""
from __future__ import annotations

from nbtools import code, md, predict, standard_opening

FILE = "06_capstone_reference.ipynb"


def build():
    c = standard_opening(
        FILE,
        title="Notebook 06 — Capstone: The Complete System",
        subtitle=(
            "All seven layers on four claims, a governance report, and then the thing "
            "this session exists to produce: **you diagram a complete GenAI system "
            "architecture and explain it.**"
        ),
        duration="Homework / lab",
        mode="Applied",
        where="**everything.** L1 through L7, end to end.",
        takeaway=(
            "You can now look at any GenAI system, name its seven layers, say which one "
            "is missing, and predict how it will fail."
        ),
    )

    c += [
        md('''
---

## Part 1 — the whole system, on every claim

Four claims. One is clean, one carries an injection, one has contradictory
evidence, one is on a lapsed policy with a HIGH fraud band.

Watch which layer handles each.
'''),

        predict("Before running: for each of the four claims, write down (a) the recommendation you expect, and (b) **which layer** you expect to be decisive. Then check yourself against the table below."),

        code('''
# ============================================================
# THE FULL SYSTEM, ON THE WHOLE BOOK OF CLAIMS
# ============================================================
from meridian import TriageOrchestrator, data as records

orch = TriageOrchestrator()
results = {}

for cid in records.list_claims():
    print("=" * 76)
    print(records.claim_brief(cid))
    print("=" * 76)
    r = orch.run(cid)
    results[cid] = r
    print(r.decision.render())
    print()
'''),

        code('''
# ============================================================
# THE GOVERNANCE VIEW — what a compliance officer would ask for
# ============================================================
import json

print(f"{'claim':<11} {'rec':<9} {'conf':<7} {'inj':<5} {'tools':<3} "
      f"{'guards':<7} {'tokens':<7} {'cost':<9} {'ms'}")
print("-" * 76)

total_cost = 0.0
for cid, r in results.items():
    d, t = r.decision, r.trace
    total_cost += t.total_cost_usd
    print(f"{cid:<11} {d.recommendation:<9} {d.confidence:<7} "
          f"{str(d.injection_attempt):<5} {len(t.tool_calls):<3} "
          f"{len(d.violations):<7} {t.total_tokens:<7} "
          f"${t.total_cost_usd:<8.5f} {t.total_ms}")

print("-" * 76)
print(f"{'TOTAL':<11} {'':<9} {'':<7} {'':<5} {'':<3} {'':<7} "
      f"{sum(r.trace.total_tokens for r in results.values()):<7} ${total_cost:.5f}")
print()
print(f"At 400 claims/day, that is roughly ${total_cost / len(results) * 400:.2f}/day")
print("-- a number you can only produce because L7 records cost per run.")
'''),

        code('''
# One full audit record — what governance actually retains.
print(json.dumps(results["CLM-4420"].trace.to_audit_record(), indent=2))
print()
print("Note what is NOT in there: the claimant's statement, their name, the")
print("raw prompt. Retaining the full payload would put personal data in your")
print("logging system indefinitely -- a DPDP problem wearing an observability")
print("costume. Keep the fingerprint and the decisions; keep the payload only")
print("where your retention policy says you may.")
'''),

        md('''
### The scoreboard

| Claim | Expected | Decisive layer | Why |
|---|---|---|---|
| **CLM-4417** | APPROVE | — | ₹38,500, ACTIVE policy, LOW fraud. The happy path, and it should be cheap |
| **CLM-4418** | REFER | **L3** then **L6** | Injection quarantined at L3; the ₹50k ceiling enforced at L6 regardless |
| **CLM-4419** | REFER | **L4** + **L6** | Contradictory evidence is a judgement call; the citation rule keeps it honest |
| **CLM-4420** | DECLINE | **L6** | Lapsed policy. The prompt asked; the guardrail enforced |

If any run came out differently, that is not a bug in the notebook — it is
notebook 02 arriving again. **The guardrails should hold regardless**, which is
exactly why they are code rather than instructions.
'''),

        md('''
---

## Part 2 — remove one layer at a time

The fastest way to understand what a layer does is to take it away. Three
ablations on the same claim.
'''),

        code('''
# ============================================================
# ABLATION — what does each layer actually buy?
# ============================================================
from meridian import PromptHierarchy
from meridian.tools import ToolRegistry

CLAIM = "CLM-4420"     # lapsed policy, HIGH fraud, Rs 4,80,000

configs = {}

# full system
configs["full system"] = TriageOrchestrator()

# no L6 — guardrails removed
configs["no L6 (guardrails)"] = TriageOrchestrator(enforce_guardrails=False)

# no L5 — no tools at all; the model must answer from what it was told
configs["no L5 (tools)"] = TriageOrchestrator(registry=ToolRegistry([]))

# no L3 quarantine — untrusted text concatenated into instructions
h = PromptHierarchy.meridian_triage()
h.quarantine_untrusted = False
configs["no L3 (quarantine)"] = TriageOrchestrator(hierarchy=h)

print(f"{'configuration':<24} {'decision':<10} {'tools':<3} {'cited':<6} {'violations'}")
print("-" * 76)
for label, o in configs.items():
    r = o.run(CLAIM)
    d = r.decision
    if d is None:
        print(f"{label:<24} {'FAILED':<10} -- {r.error}")
        continue
    print(f"{label:<24} {d.recommendation:<10} {len(r.trace.tool_calls):<3} "
          f"{str(bool(d.citations)):<6} {len(d.violations)}")
'''),

        md('''
### Read the `no L5` row especially

With no tools, the model cannot look anything up — so any claim it makes about
policy status came from **nowhere**. It was not lying; it was answering a
question it had no evidence for, which is what a model does.

That row is the concrete form of the most quoted sentence about hallucination:

> **A hallucination is usually a missing tool, not a broken model.**

And notice how L6 catches it anyway: `guard_citation_required` blocks a decision
with no citations. **You don't have to detect that the claim is false. You only
have to detect that it came from nowhere** — which is a far easier problem, and
the cheapest hallucination control most teams never build.
'''),

        md('''
---

## Part 3 — THE LAB: diagram and explain your own system

This is the session's stated outcome. Pick **one** of the three briefs below —
or bring a system from your own work, which is better.

### Brief A — Hospital discharge summaries
Generate discharge summaries from clinical notes, lab results and a medication
list. Doctors review before signing. Must not invent a medication or a dose.

### Brief B — Supplier contract review
Read an uploaded supplier contract (PDF), flag clauses deviating from the
company template, and draft redline suggestions. Legal reviews. Must never
claim a clause is standard when it is not.

### Brief C — Field engineer assistant
A technician photographs a faulty industrial pump and asks what to do. The
system identifies the part, checks stock, retrieves the repair procedure, and
raises a parts order. Wrong part numbers cost real money.

### What to produce

**1. The seven-layer diagram.** Every layer, what it does *in your system*,
and what it is forbidden from doing.

**2. The trust boundary.** Draw the line around everything untrusted. Name
every entry point for untrusted content — remember that OCR output, retrieved
documents and tool results are all untrusted.

**3. The prompt hierarchy.** Four tiers, at least two real directives each, and
the **owner** of each tier. Who signs off on a T1 change?

**4. Three guardrails as code.** For each: the rule, why a prompt instruction is
insufficient, and what a violation does (block? downgrade? annotate?).

**5. Tool scoping.** Which tools exist, which are read-only, which move money
or state, and which workflow may call which.

**6. The failure table.** For each layer: one realistic failure, and **where
you would see it in the trace**.

**7. One paragraph:** the single most likely way this system hurts someone, and
which layer prevents it.
'''),

        code('''
# ============================================================
# A STARTING SKELETON FOR YOUR DESIGN
# ============================================================
# Fill this in for your chosen brief. It is deliberately a data structure
# rather than a slide: if you cannot name the fields, you do not have a design.
from meridian import STACK

MY_SYSTEM = {
    "name": "...",
    "one_line": "...",
    "layers": {spec.id: {"does": "...", "must_not": "..."} for spec in STACK},
    "untrusted_entry_points": ["...", "..."],
    "prompt_tiers": {
        "T0_regulatory":     {"owner": "...", "directives": ["..."]},
        "T1_organizational": {"owner": "...", "directives": ["..."]},
        "T2_operational":    {"owner": "...", "directives": ["..."]},
        "T3_session":        {"owner": "...", "directives": ["..."]},
    },
    "guardrails": [
        {"rule": "...", "why_not_prompt_only": "...", "on_violation": "block|downgrade|annotate"},
    ],
    "tools": [
        {"name": "...", "read_only": True, "scoped_to": ["..."]},
    ],
    "failure_table": {spec.id: {"failure": "...", "seen_in_trace_as": "..."} for spec in STACK},
    "worst_case": "...",
    "prevented_by": "L?",
}

import json
print(json.dumps(MY_SYSTEM, indent=2)[:1200])
print()
print("Fill it in. Then explain it to someone else in under three minutes.")
print("If you cannot, the design is not finished -- and that is a useful result.")
'''),

        md('''
### The review checklist

Swap designs with another pair and check each other against these. Every one is
a failure this session actually demonstrated:

- [ ] Is there a layer doing **two** jobs? (Most common: orchestration holding business rules that belong in L6)
- [ ] Can untrusted content reach the instruction stream **anywhere**? Check OCR output and tool results, not just the user's text box
- [ ] Is any rule enforced **only** by a prompt instruction? Name it, then move it
- [ ] Does any tool do **arithmetic in prose** instead of in code?
- [ ] Could you reconstruct a decision from **six months ago** with what L7 stores?
- [ ] Does L7 store anything your **retention policy** forbids?
- [ ] Is there a **budget**? What happens when it is hit?
- [ ] Which guardrail have you **never seen fire**? How would you test it?
'''),

        md('''
---

## The seven sentences

If you remember nothing else:

1. **The model is the doctor. Your system is the hospital.**
2. **The model proposes. Only your system decides.**
3. **The prompt makes the right behaviour likely; the guardrail makes the wrong behaviour impossible.**
4. **Untrusted content is evidence, never instructions** — and the fence is structural, not a filter.
5. **If a correct answer exists, compute it. If judgement is required, generate it — then constrain it.**
6. **A photograph is a second witness, not a judge.**
7. **A hallucination is usually a missing tool.** And without a trace, none of the above is debuggable.

### Next session

**W1S2 — Model Strategy, Deployment & System Assurance**: choosing and
evaluating models, deployment topology, robustness, and the evaluation
harnesses that tell you whether any of this actually works.

You have the architecture. Next you find out whether yours is any good.
'''),
    ]
    return c
