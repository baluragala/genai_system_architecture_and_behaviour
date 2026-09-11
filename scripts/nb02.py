"""Notebook 02 — Compare ML and GenAI paradigms (20 min, conceptual)."""
from __future__ import annotations

from nbtools import code, md, predict, standard_opening

FILE = "02_ml_vs_genai.ipynb"


def build():
    c = standard_opening(
        FILE,
        title="Notebook 02 — From Deterministic ML to Probabilistic Orchestration",
        subtitle=(
            "We will **measure** the paradigm shift rather than assert it: the same "
            "claim, ten times, and a count of how often the system disagrees with itself."
        ),
        duration="20 min",
        mode="Conceptual + Guided Analysis",
        where="**L2** and **L4** — why the shape of the system changed, not just the model inside it.",
        takeaway=(
            "A traditional ML system has a **fixed shape you wrote**. A GenAI system has a "
            "**shape decided at runtime by a probabilistic component** — which is precisely "
            "why it needs orchestration, budgets and validation."
        ),
    )

    c += [
        md('''
---

## WHY — you already know how to build reliable ML systems

Most people in this room have shipped an ML system. The instincts you built
doing that are good instincts, and about half of them are now actively
misleading. Knowing *which half* is the point of the next twenty minutes.

### The analogy — the vending machine and the consultant

**A traditional ML model is a vending machine.** Fixed slots. You press B4, you
get the thing in B4. Press it a thousand times, get the same thing a thousand
times. When it's wrong, it's wrong *consistently*, which makes it debuggable.
You test it by pressing buttons and checking slots.

**An LLM is a consultant.** You describe a problem; they give you an answer.
Ask the same question tomorrow, phrased slightly differently, and you get a
different answer — possibly a better one. Both answers may be defensible.
Nobody thinks the consultant is broken.

Now: **you cannot test a consultant by pressing buttons and checking slots.**
Almost every "GenAI is unreliable" complaint is a team applying vending-machine
test methodology to a consultant.
'''),

        md('''
## WHAT — six things that changed

| | Traditional ML | GenAI system |
|---|---|---|
| **Output** | A number or a label from a fixed set | Open-ended text — infinite output space |
| **Determinism** | Same input → same output | Same input → *a distribution* over outputs |
| **Shape** | Fixed pipeline you wrote | Steps decided at runtime by the model |
| **Cost/latency** | Known before you run | Unknown until it finishes |
| **Correctness** | Measurable against labels | Often a judgement call |
| **Failure mode** | Confidently wrong *and looks wrong* | Confidently wrong *and looks right* |

The last row is the dangerous one. A broken classifier returns 0.97 for an
obviously-cat photo of a truck and your monitoring catches it. A broken LLM
returns a beautifully-written paragraph that is wrong in one clause, and your
monitoring catches nothing, because from the outside it is indistinguishable
from a correct paragraph.

### What did NOT change

Worth saying clearly, because the hype cycle implies otherwise:

- Data quality still decides everything.
- Your classical models don't go away — **they become tools.** Meridian's fraud
  model is still a gradient-boosted classifier owned by another team. The LLM
  *calls* it. GenAI is a new consumer of your ML stack, not a replacement for it.
- Deterministic code is still better than a model wherever a correct answer
  exists. Nobody should generate arithmetic.
'''),

        md('''
---

## HOW — let's measure it instead of believing it

Assertion is cheap. We will run the same claim ten times and count.

**The experiment:** `CLM-4419` — the claim where the claimant's account and
the evidence disagree, so there is genuine room for judgement. Ten runs at
temperature 0, ten at temperature 1.
'''),

        predict("Temperature 0 is often described as 'deterministic'. Across ten identical calls at temperature 0, how many *distinct* recommendations do you expect? And how many distinct rationales?"),

        code('''
# ============================================================
# EXPERIMENT 1 — determinism at temperature 0
# ============================================================
# We call the MODEL LAYER directly here, not the orchestrator: we want to
# measure the component, not the system wrapped around it.
import collections, json, textwrap
from meridian import PromptHierarchy, get_llm, data as records

claim = records.get_claim("CLM-4419")
hierarchy = PromptHierarchy.meridian_triage()

messages = hierarchy.compile(
    trusted_context={
        "claim_id": claim.claim_id,
        "policy_id": claim.policy_id,
        "claimed_amount_inr": claim.claimed_amount,
        "policy_status": "ACTIVE",          # supplied so this run needs no tools
        "sum_insured_inr": 900000,
        "fraud_band": "MEDIUM",
    },
    untrusted={"Claimant statement": claim.claimant_statement},
    user_task=f"Assess claim {claim.claim_id} and return the JSON contract.",
)

N = 10
llm_t0 = get_llm(temperature=0.0)

runs_t0 = []
for i in range(N):
    out = llm_t0.complete(messages)
    runs_t0.append(out)
    print(f"run {i+1:>2}  {out.total_tokens:>4} tok  {out.latency_ms:>5} ms")

print("\\ndone.")
'''),

        code('''
from meridian import extract_json

def summarise(runs, label):
    recs, rationales, amounts = [], [], []
    for out in runs:
        try:
            p = extract_json(out.text)
        except Exception:
            recs.append("UNPARSEABLE"); continue
        recs.append(str(p.get("recommendation", "?")).upper())
        rationales.append(str(p.get("rationale", "")).strip())
        amounts.append(p.get("assessed_amount"))

    print(f"=== {label} " + "=" * (52 - len(label)))
    print("recommendations :", dict(collections.Counter(recs)))
    print("distinct rationales :", len(set(rationales)), f"/ {len(rationales)}")
    print("distinct amounts    :", sorted({str(a) for a in amounts}))
    print("total cost          : $%.5f" % sum(o.cost_usd for o in runs))
    return recs, rationales

recs_t0, rats_t0 = summarise(runs_t0, "TEMPERATURE 0")
'''),

        md('''
### Read this carefully — it is the crux of the session

Look at the two numbers: distinct **recommendations** vs distinct
**rationales**.

You will almost certainly find that the *recommendation* is stable while the
*rationale wording* varies. That combination is the thing to internalise:

> **Temperature 0 is not a determinism guarantee. It is a greedy decoding
> strategy.**

Even at temperature 0, floating-point non-associativity in batched GPU kernels,
model-version rollouts and load-dependent routing all mean identical inputs can
produce different tokens. OpenAI's `seed` parameter is explicitly *best-effort*.

**What this means architecturally:**

- You cannot write `assert output == expected` over a model's text. That test
  will go red on a Tuesday for no reason and your team will start ignoring it —
  which is worse than not having it.
- You *can* assert over the **structured, validated fields**: the enum, the
  numeric bounds, the required citations. That is L6's contract doing double
  duty as your test surface.
- **Stability is a property you engineer**, at L6, not a property you receive
  from the model layer.
'''),

        predict("Now temperature 1.0, same prompt. How many distinct *recommendations* out of ten? Will the claimed-amount assessment vary too?"),

        code('''
# ============================================================
# EXPERIMENT 2 — the same prompt at temperature 1.0
# ============================================================
llm_t1 = get_llm(temperature=1.0)

runs_t1 = [llm_t1.complete(messages) for _ in range(N)]
recs_t1, rats_t1 = summarise(runs_t1, "TEMPERATURE 1.0")

print()
print("side by side")
print("  T=0.0 recommendations:", collections.Counter(recs_t0))
print("  T=1.0 recommendations:", collections.Counter(recs_t1))
'''),

        md('''
### The architectural consequence

If your system's recommendation can differ between two identical requests, then
**your system has no single answer — it has a distribution**, and every
downstream design decision has to account for that:

| Decision | Vending-machine thinking | Consultant thinking |
|---|---|---|
| Testing | `assert out == expected` | Assert invariants over N runs; test the *contract*, not the prose |
| Caching | Cache the output | Cache on a semantic key; decide whether variance is a feature |
| SLAs | "99.9% accurate" | "99.9% of outputs satisfy these named invariants" |
| Incidents | Reproduce locally | Reproduce **from the trace** — the input alone is not enough |
| Rollout | Swap the model | Re-run the eval set; a "better" model can break a working prompt |

That last row surprises teams. A stronger model is a *different* model. It
reads your prompt differently, weighs your instructions differently, and can
regress behaviour that was working. **Model upgrades are breaking changes**
until your eval set says otherwise.
'''),

        md('''
---

## The contrast, made concrete: the same task, deterministically

Meridian already had a rules engine for this. It is about fifteen lines, it
runs in microseconds, it costs nothing, and it is perfectly reproducible.

Run it and compare — because the honest architectural question is not "is
GenAI better?" but **"which part of this problem is each approach good at?"**
'''),

        code('''
# ============================================================
# THE DETERMINISTIC BASELINE — what Meridian had before
# ============================================================
def rules_engine(claim_id: str) -> dict:
    """Fifteen lines. Microseconds. Free. Perfectly reproducible."""
    claim  = records.get_claim(claim_id)
    policy = records.get_policy(claim.policy_id)
    fraud  = records.get_fraud(claim_id)

    if policy.status != "ACTIVE":
        return {"recommendation": "DECLINE", "reason": f"policy {policy.status}"}
    if fraud["band"] == "HIGH":
        return {"recommendation": "REFER", "reason": "fraud band HIGH"}
    if claim.claimed_amount > 50_000:
        return {"recommendation": "REFER", "reason": "above auto-approval ceiling"}
    return {"recommendation": "APPROVE", "reason": "within limits, low fraud risk"}

for cid in records.list_claims():
    out = rules_engine(cid)
    print(f"{cid}  {out['recommendation']:<8} {out['reason']}")

print()
print("Run this cell a thousand times. Identical output every time. $0.00.")
'''),

        md('''
### So why use a model at all?

Look at what the rules engine **cannot** do, and notice that none of it is
about the decision itself:

- It cannot read the claimant's paragraph and notice the incident description
  contradicts the invoice.
- It cannot look at a photograph.
- It cannot write the two-sentence explanation that goes to the claimant.
- It cannot say *"the garage estimate lists a windscreen, but no windscreen
  damage is described anywhere"* — a novel observation nobody wrote a rule for.
- It cannot handle the claim type nobody anticipated.

And look at what the model cannot do: **enforce the ceiling.** The rules engine
does that perfectly, every time, for free.

> **This is the real architecture of a production GenAI system:
> deterministic where a correct answer exists, probabilistic where judgement
> is required, and a hard boundary between them.**

That boundary has a name. It is L6, and in Meridian's stack the rules engine
*is* the guardrail layer — which is why `validation.py` re-implements those
same three checks in code even though the prompt already states them.
'''),

        md('''
---

## Why orchestration, specifically

Now the agenda's actual question: *why do GenAI systems need orchestration
beyond a traditional ML pipeline?*

A traditional pipeline:

```
features → model.predict() → post-process → done
```

Three steps. Always three. You wrote them. Cost and latency known in advance.

A GenAI system:

```
prompt → model → "call lookup_policy" → run it → feed back
               → model → "call compute_payout" → run it → feed back
               → model → answer → validate → maybe reject → maybe retry
```

**The number of steps was decided at runtime by a probabilistic component.**
Everything follows from that one sentence:

| Because… | You need… | Which lives in… |
|---|---|---|
| Cost and latency are unknown in advance | **budgets** | L2 |
| The model may never decide it's finished | **termination conditions** | L2 |
| Any step can fail | **retries that don't loop forever** | L2 |
| The output is a proposal, not a decision | **validation as a pipeline stage** | L6 |
| You can't reproduce from the input alone | **traces** | L7 |

Let's watch the step count actually vary.
'''),

        code('''
# ============================================================
# THE SHAPE IS DECIDED AT RUNTIME — watch the step count vary
# ============================================================
from meridian import TriageOrchestrator

orch = TriageOrchestrator()

for cid in ["CLM-4417", "CLM-4419", "CLM-4420"]:
    r = orch.run(cid)
    tools = r.trace.tool_calls
    print(f"{cid}   model calls: {r.trace.model_calls}   "
          f"tool calls: {len(tools):<2} {tools}")
    print(f"            tokens: {r.trace.total_tokens:<6} cost: ${r.trace.total_cost_usd:.5f}  "
          f"latency: {r.trace.total_ms} ms")
    print(f"            -> {r.decision.recommendation}")
    print()

print("Nobody wrote 'call lookup_policy, then fraud_signal, then compute_payout'.")
print("The model worked out the sequence, per claim, at runtime.")
print("That is the thing a traditional pipeline never does — and the reason")
print("L2 has to own budgets and termination.")
'''),

        md('''
### Notice what would happen with no L2

If nothing owned termination, a model that decides to call `lookup_policy` on
every turn would call it forever. That is not a hypothetical failure — it is
one of the two most common production incidents in agentic systems (the other
being no budget at all, discovered via the invoice).

Look at `Budget` in `meridian/orchestrator.py`:

```python
max_model_calls  = 6
max_tool_calls   = 8
max_tokens       = 20_000
max_repair_attempts = 1
```

Deliberately small numbers. **A budget you never hit is a budget you have not
tested**, and the first time you hit one should not be in production at
month-end.
'''),

        md('''
---

## Exercise — classify these five requirements (5 min)

For each, decide: **deterministic code, model, or model + guardrail?**

1. "Reject any claim submitted more than 90 days after the incident."
2. "Summarise the claimant's account in two sentences for the adjuster's queue."
3. "Never approve above ₹50,000."
4. "Flag when the garage invoice lists parts inconsistent with the described damage."
5. "Compute the payable amount after depreciation and deductible."

<details>
<summary>Answers — discuss first</summary>

1. **Deterministic.** A date comparison. Using a model here is slower, costlier and less reliable.
2. **Model.** Open-ended language generation, no single correct answer. Exactly the right job.
3. **Deterministic guardrail (L6).** State it in the prompt *too*, but enforcement must be code.
4. **Model + guardrail.** Only a model can spot a novel inconsistency; a guardrail requires the finding be cited to a source so it can be checked.
5. **Deterministic tool (L5).** Arithmetic has a correct answer. `compute_payout` exists precisely so the model never does this in prose.

The reusable rule: **if a correct answer exists, compute it. If judgement is
required, generate it — then constrain it.**
</details>
'''),

        md('''
---

## Where we are, and what's next

You have *measured* the shift rather than taken it on faith: the same input,
the same model, different outputs — and a system shape decided at runtime.

**The takeaway again:**
> A traditional ML system has a **fixed shape you wrote**. A GenAI system has a
> **shape decided at runtime by a probabilistic component** — which is exactly
> why orchestration, budgets and validation stop being optional.

Next: the layer that most teams treat as a string and that is actually an
access-control system. Notebook 03 is 30 minutes on prompting **as architecture**.

### Before you move on
- [ ] Can you explain why temperature 0 is not a determinism guarantee?
- [ ] Can you state what you *can* safely assert in a test over model output?
- [ ] Can you name the five things L2 must own, and why each follows from runtime-decided step counts?
'''),
    ]
    return c
