# Learner Handout — GenAI System Architecture & Behaviour

**Print this. Keep it next to you during the session.**

> ## The one sentence
> **The model is the doctor. Your system is the hospital.**
> Nobody ships a doctor standing in a field.

---

## The seven layers

| # | Layer | Owns | Must NOT | Fails like | In the trace |
|---|---|---|---|---|---|
| **L1** | Experience / Interface | channel adaptation, auth, rate limits, payload size | make decisions | a 14 MB sideways photo reaches the model | intake span with an odd size or content type |
| **L2** | Orchestration | step sequencing, retries, **budgets**, termination, routing | hold business rules that belong in L6 | the model loops; nothing owns "enough" | the same L5 span repeated, no budget span |
| **L3** | Context & Prompt | instruction tiers, **quarantine**, context assembly, versioning | put tool results in the system prompt as instructions | a claimant's sentence is read as a policy change | a fingerprint that changed with no release |
| **L4** | Model | token generation, tool-call **intent** | be the source of truth for cover, limits or arithmetic | fluent, confident, wrong | an L4 span with **no L5 spans before it** |
| **L5** | Tools & Integration | schemas, descriptions, system-of-record access, deterministic computation | raise exceptions; interpret results | a not-found is ignored; the model answers from memory | `ok=false` followed by an answer anyway |
| **L6** | Validation & Guardrails | schema validation, limits, refusal, downgrade, citations | **upgrade** a decision; silently rewrite output | there is no L6, so the model's worst day is yours | a decision released with no checks run |
| **L7** | Observability & Governance | traces, fingerprints, cost, audit, retention | retain data your policy forbids | "it worked last Tuesday" and no way to know | **the absence of a trace** |

### The two boundaries teams think they have

- **L4 / L6** — "the model decides." No. **The model proposes.**
- **L3 / L5** — "just put the data in the prompt." Facts enter via **L5** and get
  **cited**. Instructions enter via **L3** and get **tiered**.

---

## The prompt hierarchy

| Tier | Who may change it | Example |
|---|---|---|
| **T0 Regulatory** | Nobody | "Never imply a settlement is guaranteed" |
| **T1 Organizational** | Compliance, at release | "Auto-approval ceiling is ₹50,000" |
| **T2 Operational** | The workflow author | "Motor own-damage claims only" |
| **T3 Session** | The adjuster, per run | "Explain simply; claimant is elderly" |
| **UNTRUSTED** | claimant text, OCR, retrieved docs, **tool results** | **Fenced. Never instructions.** |

**The tier is decided by where the content ENTERED the system** — not by how
senior the author sounds.

**Two rules:**
1. Higher tiers win, and the precedence rule is stated *inside* the prompt.
2. Untrusted content is quarantined, with surrounding instructions — from a tier
   the attacker cannot reach — declaring what that block is.

> **You cannot regex your way out of prompt injection.** Blocklists enumerate
> the attacks you thought of. Structural quarantine is the parameterised-SQL
> move: make data structurally incapable of becoming code.

---

## Six perceptual failure modes (multimodal)

| Mode | Example | Control |
|---|---|---|
| **Resolution loss** | Is that ₹79,886 or ₹19,886? | Ask for `legibility` as a **separate field** |
| **Ambiguity** | A tick between two boxes | Make `"ambiguous"` an allowed answer |
| **Cross-modal contradiction** | Text says front; photo shows rear | Extract **per-source first**, reconcile second |
| **Spatial reasoning** | "Which side?" | Anchor to landmarks that don't flip |
| **OCR confusion** | 1/7, 0/O, 1,94,000 vs 194,000 | Never let vision be the sole source of a number |
| **Confident hallucination** | A plate number in a photo with no plate | Require a grounding phrase per assertion |

> **A photograph is a second witness, not a judge.** A contract with no escape
> hatch forces a guess.

---

## Protocols (MCP)

```
   without a protocol :  N apps × M tools  =  N × M integrations
   with a protocol    :  N clients + M servers  =  N + M
```

**The kettle doesn't know where the electricity came from.** That ignorance is
the entire value.

| You gain | You pay |
|---|---|
| Discovery, versioning, isolation, authority, reuse | Serialisation, a process to supervise, a new failure surface, harder debugging, latency |

**Use it when:** another team owns the tool · the tool outlives the app ·
several apps need it · it needs its own release cadence.
**Don't when:** it's three functions in one codebase with one consumer.

> A protocol solves **plumbing**, never **meaning**. If a tool's semantics
> change, every consumer breaks regardless — that needs **versioning**.

---

## Traditional ML vs GenAI

| | Traditional ML | GenAI |
|---|---|---|
| Output | a label from a fixed set | open-ended text |
| Determinism | same in → same out | same in → **a distribution** |
| Shape | fixed pipeline you wrote | **decided at runtime by the model** |
| Cost/latency | known in advance | unknown until it finishes |
| Failure | confidently wrong **and looks wrong** | confidently wrong **and looks right** |

**Temperature 0 is not a determinism guarantee. It is a greedy decoding
strategy.**

Because the step count is decided at runtime, L2 must own: **budgets**,
**termination**, **retries**, and L6 must own **validation as a pipeline
stage**, and L7 must own **traces** (you cannot reproduce from the input alone).

> **If a correct answer exists, compute it. If judgement is required, generate
> it — then constrain it.**

---

## The seven sentences

1. The model is the doctor. Your system is the hospital.
2. The model proposes. Only your system decides.
3. The prompt makes the right behaviour likely; the guardrail makes the wrong behaviour impossible.
4. Untrusted content is evidence, never instructions.
5. If a correct answer exists, compute it. If judgement is required, generate it — then constrain it.
6. A photograph is a second witness, not a judge.
7. A hallucination is usually a missing tool.

---

## Design review checklist

Use this on any GenAI system, including your own:

- [ ] Is there a layer doing **two** jobs? (Usually: L2 holding rules that belong in L6)
- [ ] Can untrusted content reach the instruction stream **anywhere**? Check OCR output and tool results, not just the text box
- [ ] Is any rule enforced **only** by a prompt instruction?
- [ ] Does anything do **arithmetic in prose** instead of in code?
- [ ] Could you reconstruct a decision from **six months ago**?
- [ ] Does L7 store anything your **retention policy** forbids?
- [ ] Is there a **budget**? What happens when it's hit?
- [ ] Which guardrail have you **never seen fire**? How would you test it?

---

## Setup

```
Colab : sidebar → key icon → add OPENAI_API_KEY → Notebook access ON
local : export OPENAI_API_KEY=sk-...
```

Run the bootstrap cell first in every notebook. There is no offline fallback —
on purpose. Cost for the whole session: a few cents.
