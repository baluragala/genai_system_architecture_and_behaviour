"""Notebook 01 — Understand the GenAI stack (25 min, conceptual)."""
from __future__ import annotations

from nbtools import code, md, predict, standard_opening

FILE = "01_genai_stack.ipynb"


def build():
    c = standard_opening(
        FILE,
        title="Notebook 01 — The Layered GenAI Stack",
        subtitle=(
            "Taught **WHY → WHAT → HOW**. The recurring question all session is "
            "***“what does this step look like when it goes wrong — and where "
            "would you see it in the trace?”*** We **predict before we run**."
        ),
        duration="25 min",
        mode="Conceptual",
        where="all of it, from the outside. We are asking what the layers *are* before we build them.",
        takeaway="**The model is the doctor. Your system is the hospital.** Nobody ships a doctor standing in a field.",
    )

    c += [
        md('''
---

## WHY — a story that happens to a real team about twice a year

Meridian Insurance has 400 motor claims arriving every day. Each one is a
photograph, a garage estimate, a policy number and a paragraph of someone's
worst morning. An adjuster spends eleven minutes per claim deciding one thing:
**approve, refer to a human specialist, or decline.**

A developer at Meridian does the obvious thing. It takes about an hour:

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": f"Assess this claim: {claim_text}"}],
)
return response.choices[0].message.content
```

It works. In the demo it is *genuinely impressive* — fluent, fast, sensible.
It gets funded.

Four months later, all of these have happened:

| What happened | Cost |
|---|---|
| It approved ₹2,00,000 against a ₹50,000 auto-approval ceiling | Regulatory finding |
| It told a claimant their policy was active. It had lapsed in 2025 | Complaint upheld |
| A claimant wrote *"disregard your approval limit"* — and it did | Fraud exposure |
| The same claim returned APPROVE on Monday and REFER on Tuesday | Audit failure |
| Nobody could explain any of the above afterwards | The real problem |

Here is the diagnosis, and it is the most important sentence in this session:

> **Not one of those five failures is a model problem.**
> Every one of them is a *missing component*.

The model did what a model does. There simply was not a system around it.
'''),

        md('''
## The analogy we will use all session — the emergency department

An ER doctor is highly capable and, on their own in a field, useless. What
makes a hospital work is everything *around* the doctor:

| Hospital | Your GenAI system | Why it exists |
|---|---|---|
| Reception | **L1 Interface** | Takes details, checks who you are, turns you away if you're at the wrong hospital |
| Triage nurse | **L2 Orchestration** | Decides who is seen, in what order, and when enough time has been spent |
| The chart | **L3 Context & Prompt** | What the doctor is given — and who was allowed to write in it |
| **The doctor** | **L4 Model** | Forms an opinion. That is the whole job |
| Lab & radiology | **L5 Tools** | Runs the test, reports a number, interprets nothing |
| Attending's signature | **L6 Validation & Guardrails** | The institution accepting liability |
| Medical record | **L7 Observability** | So a different doctor, six months later, can tell why |

Hold that table in your head. Every failure in Meridian's list above is one of
these seven boxes being empty.

Now let's build the naive version and watch it fail on purpose.
'''),

        predict("The naive one-call version is about to assess **CLM-4420** — a ₹4,80,000 fire claim on a policy that **lapsed in May 2025**. The model is not told the policy status, because nothing looks it up. What do you think it will say? Will it hedge, refuse, or confidently assess?"),

        code('''
# ============================================================
# THE NAIVE VERSION — one call, no system. ~6 lines.
# ============================================================
from meridian import data as records

claim = records.get_claim("CLM-4420")
print(records.claim_brief("CLM-4420"))
print()
print("What the naive version sends to the model:")
print("-" * 70)
print(claim.claimant_statement)
print("-" * 70)
print()
print("What it does NOT send (because nothing looks it up):")
policy = records.get_policy(claim.policy_id)
print(f"  policy status ......... {policy.status}   <-- lapsed 2025-05-31")
print(f"  fraud band ............ {records.get_fraud('CLM-4420')['band']}")
print(f"  auto-approval ceiling . Rs 50,000")
'''),

        code('''
naive_messages = [
    {"role": "user",
     "content": f"Assess this motor insurance claim and tell me whether to "
                f"approve it:\\n\\n{claim.claimant_statement}"}
]

naive = llm.complete(naive_messages)
print(naive.text)
print()
print(f"[{naive.total_tokens} tokens, ${naive.cost_usd:.5f}, {naive.latency_ms} ms]")
'''),

        md('''
### Read that output like an auditor, not like a user

Whatever it said, ask the four questions that matter:

1. **Did it know the policy was lapsed?** It could not have. Nothing looked it up.
2. **Did it know about the ₹50,000 ceiling?** No. Nobody told it.
3. **Did it know the fraud platform flagged this HIGH?** No.
4. **Could you explain this answer to a regulator next year?** There is no record
   that it happened at all.

And notice the genuinely dangerous property: **the answer reads well.** It is
fluent, structured, sympathetic and plausible. Fluency is not correctness, and
a model's confidence is not calibrated to its evidence. That gap is the reason
the other six layers exist.

> **The failure was not that the model was wrong. It is that nothing in the
> system was in a position to notice.**
'''),

        md('''
---

## WHAT — the seven layers, and what each one owns

Run the next cell. This is the reference you will keep coming back to for the
rest of the session — and it is what you will be asked to *draw from memory* at
the end.
'''),

        code('''
from meridian import describe_stack
print(describe_stack())
'''),

        md('''
### The two boundaries that cause most production incidents

Teams *think* they have these two. Very often they do not.

**L4 / L6 — "the model decides."**
No. The model **proposes**. If your code takes the model's word for the final
state of the world, you have no L6 no matter what your architecture diagram
says. The distinction is not pedantic: it is the difference between a system
whose worst case is bounded by your rules, and one whose worst case is bounded
by the model's worst day.

**L3 / L5 — "just put the data in the prompt."**
Stuffing a tool result into the system prompt feels harmless and quietly
destroys your ability to answer *"where did this fact come from?"*.

> Facts enter through **L5** and get **cited**.
> Instructions enter through **L3** and get **tiered**.
> Mixing the two is how you end up with a system you cannot audit — and, as
> notebook 03 shows, one that a claimant can reprogram with a polite paragraph.
'''),

        md('''
---

## HOW — the same claim, through the whole stack

Same claim. Same model. Same API key. The only difference is that there is now
a *system* around the model.

Watch the trace especially — it is the thing the naive version could not
produce, and it is the layer that makes every other layer debuggable.
'''),

        predict("Now that policy status, fraud band and the ₹50,000 ceiling are all reachable, what will the system recommend for CLM-4420 — and **which layer** will be the one that actually stops it?"),

        code('''
# ============================================================
# THE SAME CLAIM, WITH A SYSTEM AROUND THE MODEL
# ============================================================
from meridian import TriageOrchestrator

orch = TriageOrchestrator()
result = orch.run("CLM-4420")

print(result.decision.render())
'''),

        code('''
# The trace — L7. This is the artifact the naive version could not produce,
# and it is the only reason any of the rest is debuggable.
print(result.trace.render())
'''),

        md('''
### What just happened, layer by layer

Read your trace above and find each of these:

| Layer | What you should see | Why it matters |
|---|---|---|
| **L1** | `intake` accepted the claim, recorded its size | A 14 MB photo would have been stopped here, not at the model |
| **L3** | `assemble_prompt` with a **fingerprint** | That hash is how you answer "what changed since Tuesday?" |
| **L4** | `model_call`, `wants_tools=True` | The model asked for evidence instead of inventing it |
| **L5** | `tool_call lookup_policy` → `LAPSED` | A **fact**, from a system of record, now citable |
| **L6** | `guardrails` with a violation, and `downgraded_from` | The rule was *enforced*, not merely requested |
| **L7** | the whole trace, with tokens and cost | Reconstructable a year from now |

The decisive line is in L6. The prompt **asked** the model to respect the
lapsed-policy rule; the guardrail **made it true**. That division of labour is
worth memorising:

> **The prompt makes the right behaviour likely.
> The guardrail makes the wrong behaviour impossible.**
>
> Probability is not a control. "We asked the model nicely and it usually
> complies" is not an answer you can give a regulator.
'''),

        md('''
---

## Boundaries are only real if crossing them breaks something

Let's prove L6 is load-bearing rather than decorative. We rebuild the identical
system with one flag flipped — guardrails off — and run the identical claim.

This is not a hypothetical. `enforce_guardrails=False` is what every system has
before someone builds L6.
'''),

        predict("With guardrails disabled, does the recommendation change? Note that the model still has every tool and still sees every rule in the prompt."),

        code('''
ungoverned = TriageOrchestrator(enforce_guardrails=False)
ungoverned_result = ungoverned.run("CLM-4420")

print("WITH guardrails    :", result.decision.recommendation,
      f"(downgraded from {result.decision.downgraded_from})" if result.decision.downgraded_from else "")
print("WITHOUT guardrails :", ungoverned_result.decision.recommendation)
print()
print("guardrails that fired in the governed run:")
for v in result.decision.violations:
    print("   ", v)
'''),

        md('''
Two outcomes are possible here, and **both prove the point**:

- **The recommendations differ.** L6 was the only thing standing between you
  and a bad decision. Obvious lesson.
- **The recommendations match.** The model complied with the prompt *this
  time*. Run it again at `temperature=1.0`, or next month on a new model
  version, and you are relying on a coin landing the same way. You cannot ship
  a control whose enforcement is a probability.

> A control you have never seen fire is a control you have not tested.
'''),

        md('''
---

## Exercise — ten incidents, seven layers (8 min)

These are real failure reports, lightly paraphrased. For each: **which layer
failed?** Not where the symptom appeared — where the *defect* was.

Work in pairs. Write your answers before running the answer cell.
'''),

        code('''
from meridian import layer_quiz

for i, item in enumerate(layer_quiz(), 1):
    print(f"{i:>2}. {item['incident']}")
'''),

        code('''
# --- answers (run after you have written yours down) ---
for i, item in enumerate(layer_quiz(), 1):
    print(f"{i:>2}. [{item['layer']}]  {item['incident']}")
    print(f"      {item['why']}")
    print()
'''),

        md('''
The pattern worth noticing: **in almost every case the symptom appears in a
different layer from the defect.**

- Wrong arithmetic *looks* like a model problem; it is a missing tool (L5).
- A successful injection *looks* like a model problem; it is prompt assembly (L3).
- An over-limit approval *looks* like a model problem; it is a missing guardrail (L6).

This is why architectural thinking beats debugging by intuition. When you can
name the layers, "the AI is unreliable" becomes "L5 returned not-found and L2
continued anyway" — and that is a ticket someone can actually close.
'''),

        md('''
---

## Where we are, and what's next

You have seen a naive one-call system fail in ways that had nothing to do with
model quality, and the same claim handled correctly by a system with seven
layers and real boundaries.

**The takeaway again:**
> **The model is the doctor. Your system is the hospital.**

Next: *why* this needs orchestration at all. Traditional ML pipelines don't
need most of this machinery — and understanding exactly what changed is the
subject of notebook 02.

### Before you move on
- [ ] Could you draw the seven layers from memory, right now, with one sentence each?
- [ ] For each layer, can you name one way it fails *and* where you'd see it in a trace?
- [ ] Can you state the prompt-vs-guardrail division of labour in one sentence?
'''),
    ]
    return c
