# Design — GenAI System Architecture & Behaviour (C8W1S1)

**Date:** 2026-09-11
**Session:** GenAI – C8W1S1, 120 minutes
**Status:** Approved, implementing

---

## Purpose

A hands-on teaching package for the 120-minute live session *"GenAI System
Architecture & Behaviour"*. The agenda is explicit that the subject is **system
design thinking, not model internals** — so the package must teach architecture
through a system the learner watches get built, not through slides about
architecture.

The session's stated outcome is that learners can **diagram and explain a
complete GenAI system architecture**. Every design decision below is in service
of that one sentence.

## Constraints (decided with the instructor)

| Decision | Choice | Consequence |
|---|---|---|
| Domain | Insurance claims triage — "Meridian Insurance" | High-stakes, regulated, naturally multimodal, and *triage* rhymes with the spine analogy |
| Model access | **OpenAI, API key required, no fallback** | Every notebook cell calls a real model. A simulated model teaches the shape of a system while misrepresenting the probabilistic behaviour the session is about |
| Deliverables | Full package: notebooks + package + teaching + slides | Matches `agentic-systems-foundations` house style |
| Runtime | Google Colab first, local Jupyter second | Bootstrap cell installs by import-check and clones the repo when in Colab |

## Pedagogy

Three rules, applied to every notebook:

1. **WHY → WHAT → HOW.** Motivate the problem before naming the concept before
   showing the code.
2. **Predict before you run.** Every significant cell is preceded by a
   prediction prompt. Being wrong out loud is the lesson.
3. **Every concept carries an analogy.** Architecture is invisible; analogies
   are the only handle a learner gets in a 120-minute room.

### The spine analogy — a hospital emergency department

Claims triage *is* triage, so the analogy is structural rather than decorative.
It carries all five agenda blocks:

| Block | Concept | Analogy |
|---|---|---|
| 1 | Layered stack | **The model is the doctor. Your system is the hospital.** Nobody ships a doctor standing in a field |
| 2 | ML → GenAI shift | Vending machine (fixed SKUs, deterministic) vs. a consultant who improvises |
| 3 | Prompt hierarchy | Regulation > hospital policy > attending's brief > patient's request. **The patient does not get to rewrite the law** |
| 4 | Multimodal | A photograph is a *second unreliable narrator* — another witness who can be confidently wrong |
| 5 | Protocols / MCP | Electrical sockets. The appliance never knows the power plant |

## Architecture

### The seven layers

The package's core claim is that a GenAI system is seven layers with enforced
boundaries, and that most production incidents are a boundary that was never
drawn. Each layer is a real Python object with one responsibility.

| # | Layer | Responsibility | ER analogy |
|---|---|---|---|
| L1 | Experience / Interface | Accept intake, shape the response for a channel | Reception desk |
| L2 | Orchestration | Decide what happens in what order; own control flow | Triage nurse |
| L3 | Context & Prompt | Assemble what the model sees, with precedence | The chart handed to the doctor |
| L4 | Model | Inference. **Nothing else** | The doctor |
| L5 | Tools & Integration | Reach into systems of record | Lab and radiology |
| L6 | Validation & Guardrails | Enforce the output contract and policy | Attending's sign-off |
| L7 | Observability & Governance | Trace, cost, audit | The medical record and the hospital's audit |

**Data flow** — one path, each layer touching only its neighbours:

```
claim intake → validation → prompt assembly (hierarchy) → model
            → tool calls (MCP) → output contract check → guardrails → decision + trace
```

### Package modules

```
meridian/
  config.py         OpenAI adapter; key required; temperature 0; usage capture
  data.py           Synthetic policies, claims, fraud signals
  layers.py         The seven layers as objects with real boundaries
  prompts.py        PromptHierarchy — four precedence tiers + quarantined untrusted input
  multimodal.py     Deterministic asset rendering (PIL) + structured multimodal envelope
  tools.py          Tool registry, JSON-Schema contracts, three claim tools
  mcp_server.py     A real MCP stdio server exposing the same three tools
  mcp_client.py     Subprocess bridge; works inside a Colab event loop
  validation.py     Output contract (pydantic) + guardrail chain
  observability.py  Trace / Span / cost accounting, renderable in a notebook
  orchestrator.py   Wires the seven layers into one runnable system
```

### Prompt hierarchy — four tiers plus a quarantine

The single most important teaching artifact in the package.

| Tier | Name | Mutable by | Example |
|---|---|---|---|
| T0 | Regulatory | Nobody | "Never state or imply a final settlement figure as guaranteed" |
| T1 | Organizational | Compliance, at release time | "Auto-approval ceiling is ₹50,000" |
| T2 | Operational | The workflow author | "You are triaging a motor claim. Produce the ClaimDecision contract" |
| T3 | Session | The adjuster | "Explain in Hindi-English mix; the claimant is a senior citizen" |
| — | **Untrusted** | The claimant, documents, OCR | **Never instructions. Data only, inside a delimited block** |

Notebook 03 demonstrates that prompt injection is not a model problem but an
**architecture** problem: remove the quarantine and the same claimant text that
failed a moment ago now succeeds in raising its own payout.

### Multimodal assets are generated, not shipped

`multimodal.py` renders the claim form, repair invoice and damage diagram with
PIL at runtime. Three reasons:

1. No licensing question, no binary blobs in the repo.
2. Deterministic — every learner in the room sees the identical artifact.
3. **The failure is injectable.** The agenda asks for *perceptual failure
   modes*; a stock photo only contains one if you are lucky. Here a smudged
   `7`/`1`, a checkbox straddling two boxes, and a text/image contradiction are
   placed on purpose.

### MCP is real, not simulated

`mcp_server.py` is an actual stdio MCP server launched as a subprocess. A
simulated protocol teaches the vocabulary while hiding the entire point — the
**process boundary**. Notebook 05 swaps hand-rolled tool calling for the MCP
server and shows the rest of the system does not change, which is the
definition of a protocol.

## Notebooks

| NB | Agenda block | Min | What gets built |
|---|---|---|---|
| 01 | Understand GenAI stack | 25 | Naive one-call triage → decomposed into seven layers |
| 02 | Compare ML and GenAI paradigms | 20 | Same claim 10×, temp 0 vs 1; disagreement measured; contrasted with a deterministic classifier |
| 03 | Design system prompting strategies | 30 | Four-tier hierarchy; injection defeated, then the quarantine removed and injection succeeds |
| 04 | Analyse multimodal complexity | 20 | Three rendered artifacts; cross-modal contradiction; six perceptual failure modes |
| 05 | Understand protocols & interoperability | 25 | Hand-rolled tools → real MCP stdio server, system unchanged |
| 06 | Capstone | homework | Full governed pipeline + "diagram your own system" lab |

## Testing

`pytest` over the package, with the model adapter stubbed **at the boundary**
— the tests stub it, the notebooks never do. Notebooks additionally carry a
smoke path so the instructor can verify the whole session runs before teaching.

## Out of scope

Fine-tuning, RAG retrieval quality, deployment topology, and evaluation
harnesses — all of which belong to W1S2 (*Model Strategy, Deployment & System
Assurance*) and are deliberately left for it.
