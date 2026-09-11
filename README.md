# GenAI System Architecture & Behaviour

A complete, hands-on teaching package for the 120-minute live session
**"GenAI System Architecture & Behaviour"** (GenAI — C8W1S1).

The agenda is explicit that the subject is **system design thinking, not model
internals**. So this package does not lecture about architecture — it builds a
real system in front of the room, one layer at a time, and breaks it on purpose
four times.

> ## The one takeaway
> **The model is the doctor. Your system is the hospital.**
> Nobody ships a doctor standing in a field.

---

## The system: Meridian Insurance claims triage

Every notebook works on the same thing — an automated motor-claims triage
system for a fictional Indian insurer. 400 claims a day, each one a photograph,
a garage estimate, a policy number and a paragraph of someone's worst morning.
The system must decide: **approve, refer, or decline.**

Claims triage was chosen deliberately: it is high-stakes, regulated, naturally
multimodal, and — usefully — *triage* is exactly what an emergency department
does, which is the analogy the whole session runs on.

Four claims carry a planted trap. They are the teaching material:

| Claim | The trap | Taught in |
|---|---|---|
| `CLM-4417` | none — the happy path | 01 |
| `CLM-4418` | a **prompt injection** hidden in fluent, plausible prose | 03 |
| `CLM-4419` | text, photo and invoice **contradict each other** | 04 |
| `CLM-4420` | lapsed policy, ₹4,80,000, HIGH fraud band | 01, 06 |

If the system ever approves `CLM-4418` or `CLM-4420`, something in the
architecture is broken — and finding out *which layer* is the exercise.

---

## The seven layers

Layer diagrams are the most-drawn and least-believed artifact in our industry.
Here the layers are **real objects with real boundaries**, so when a notebook
violates one on purpose, something actually breaks.

| # | Layer | ER analogy | Module |
|---|---|---|---|
| **L1** | Experience / Interface | reception desk | `orchestrator._intake` |
| **L2** | Orchestration | triage nurse | `orchestrator.py` |
| **L3** | Context & Prompt | the chart — and who wrote in it | `prompts.py` |
| **L4** | Model | **the doctor** | `config.py` |
| **L5** | Tools & Integration | lab & radiology | `tools.py`, `mcp_*.py` |
| **L6** | Validation & Guardrails | the attending's signature | `validation.py` |
| **L7** | Observability & Governance | the medical record | `observability.py` |

```
claim intake → validation → prompt assembly (hierarchy) → model
            → tool calls (MCP) → output contract check → guardrails → decision + trace
```

---

## The notebooks

Each maps to one agenda block, timeboxed to match.

| # | Notebook | Agenda block | Min | What gets built |
|---|---|---|---|---|
| 01 | `01_genai_stack.ipynb` | Understand GenAI stack | 25 | A naive one-call triage, then the same claim through seven layers |
| 02 | `02_ml_vs_genai.ipynb` | Compare ML and GenAI paradigms | 20 | The same claim 10× at T=0 and T=1; disagreement **measured**, not asserted |
| 03 | `03_prompt_architecture.ipynb` | Design system prompting strategies | 30 | An injection defeated — then the quarantine removed and the same injection succeeds |
| 04 | `04_multimodal.ipynb` | Analyse multimodal complexity | 20 | Three contradictory artifacts and six perceptual failure modes |
| 05 | `05_protocols_and_mcp.ipynb` | Understand protocols & interoperability | 25 | Tools moved behind a **real MCP stdio server**; one line changes, nothing else does |
| 06 | `06_capstone_reference.ipynb` | — | homework | Full governed pipeline, layer ablations, and "diagram your own system" |

### Three demos that *are* the session

Cut anything else first:

1. **NB01's ablation** — guardrails on vs off, same claim.
2. **NB03's quarantine removal** — one line, and the attack lands.
3. **NB05's registry swap** — in-process → separate process, one line.

---

## Quick start

### Colab (what learners use)

Open any notebook with its **Open in Colab** badge, then:

```
sidebar → key icon → add a secret named OPENAI_API_KEY → Notebook access ON
```

Run the bootstrap cell first. It installs what's missing and clones the repo.

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...

pytest                    # 56 tests, ~2s — the system, with a stubbed model
python scripts/smoke.py   # your key, the vision path, and MCP — ~half a cent
jupyter lab notebooks/
```

**Instructors: run `scripts/smoke.py` the day before, not the morning of.**
`pytest` proves the system works; `smoke.py` proves *your key* does.

---

## Why there is no offline fallback

Every notebook calls a real model. An API key is required, deliberately.

A simulated model can show you the *shape* of a layered system while quietly
misrepresenting the one property this entire session is about: that L4 is
**probabilistic**. Notebook 02 runs the same claim ten times and counts how
often the system disagrees with itself. A stub would answer identically every
time and teach a comfortable lie.

Cost for the whole session: **roughly $0.05–0.15 per learner** at gpt-4o-mini
prices. Notebook 02 is about 60% of it.

---

## What's in the box

```
genai_system_architecture_and_behaviour/
├── meridian/                 # the system under construction
│   ├── config.py             #   L4 — the ONLY module that knows OpenAI exists
│   ├── data.py               #   systems of record + the four planted traps
│   ├── layers.py             #   the seven layers as data + the 10-incident quiz
│   ├── prompts.py            #   L3 — PromptHierarchy, 4 tiers + the quarantine
│   ├── multimodal.py         #   PIL-rendered evidence + 6 perceptual failure modes
│   ├── tools.py              #   L5 — registry, JSON-Schema contracts, 3 tools
│   ├── mcp_server.py         #   a REAL MCP stdio server exposing the same tools
│   ├── mcp_client.py         #   the socket side; works inside Colab's event loop
│   ├── validation.py         #   L6 — output contract + the guardrail chain
│   ├── observability.py      #   L7 — Trace, cost accounting, audit records
│   └── orchestrator.py       #   L2 — the whole system, in one readable method
├── notebooks/  01–06
├── teaching/
│   ├── instructor_guide.md   #   timing, what will go wrong, the questions you'll be asked
│   ├── learner_handout.md    #   print this
│   ├── exercises.md
│   └── solutions/solutions.md#   incl. the lab assessment rubric
├── slides/                   # self-contained HTML deck for live delivery
├── scripts/                  # notebook builder + the pre-flight smoke check
├── tests/                    # 56 tests; MCP ones spawn a real subprocess
└── docs/superpowers/specs/   # the design document
```

### Notebooks are generated, not hand-edited

```bash
python scripts/build_notebooks.py
```

Edit `scripts/nb0*.py` and rebuild. Generating them keeps the shared cells —
the Colab badge, the bootstrap, the key check — byte-identical across all six.
In a live session, *"notebook 4's bootstrap is subtly different"* is a
ten-minute detour nobody planned for.

**Before publishing, set `REPO` at the top of `scripts/nbtools.py` to your
fork** and rebuild — it is what the *Open in Colab* badges and the bootstrap
cell's `git clone` both point at.

---

## Design decisions worth knowing about

**Multimodal assets are rendered, not shipped.** `multimodal.py` draws the claim
form, repair invoice and damage photo with PIL at runtime. No binary blobs, no
licensing question, and — the real reason — **the defects are injectable**. The
agenda asks for *perceptual failure modes*; a stock photograph contains one only
if you are lucky. Here the smudged digit, the checkbox straddling two boxes and
the text/image contradiction sit at known coordinates and reproduce every run.

**MCP is real, not simulated.** `mcp_server.py` is an actual stdio server the
notebook launches as a subprocess. A simulated protocol teaches the vocabulary
while hiding the entire point — the **process boundary**.

**No orchestration framework.** The orchestrator is ~200 readable lines. Both of
these are true and you need both: you should not hand-roll orchestration in
production, *and* a framework will not make a single design decision for you.
**The framework abstracts the mechanics, not the design.** We hand-rolled it so
the mechanics are visible.

**Tests stub the model; notebooks never do.** Every test asserts on a validated
contract field or a guardrail firing — never on generated prose. That is not
just convenience, it is notebook 02's argument written out as a testing
strategy.

---

## The seven sentences

1. **The model is the doctor. Your system is the hospital.**
2. **The model proposes. Only your system decides.**
3. **The prompt makes the right behaviour likely; the guardrail makes the wrong behaviour impossible.**
4. **Untrusted content is evidence, never instructions.**
5. **If a correct answer exists, compute it. If judgement is required, generate it — then constrain it.**
6. **A photograph is a second witness, not a judge.**
7. **A hallucination is usually a missing tool.**

---

## Next session

**W1S2 — Model Strategy, Deployment & System Assurance.** Choosing and
evaluating models, deployment topology, robustness, and the evaluation
harnesses that tell you whether any of this actually works.

You have the architecture. Next you find out whether yours is any good.
