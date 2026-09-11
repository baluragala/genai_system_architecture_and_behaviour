# Instructor Guide — GenAI System Architecture & Behaviour (C8W1S1)

**120 minutes. Five blocks. One system, built in front of the room.**

---

## Before you teach

### The 15-minute pre-flight (do this the day before, not the morning of)

```bash
git clone <repo> && cd genai_system_architecture_and_behaviour
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...

pytest                      # 56 tests, ~2s. All must pass.
python scripts/smoke.py     # runs one real claim end to end + MCP round trip
```

`pytest` uses a stubbed model, so it proves the *system* works but not that
your key does. `scripts/smoke.py` spends about half a cent and proves both.

**Then open `notebooks/02_ml_vs_genai.ipynb` and run it fully.** It is the most
expensive notebook (20 real model calls) and the one most likely to surprise
you, because its output genuinely differs between runs. Know what your room is
about to see.

### Cost

The whole session is roughly **$0.05–0.15 per learner** at gpt-4o-mini prices.
Notebook 02 is ~60% of it. If your cohort is large and sharing one key, run
notebook 02 yourself on the shared screen and have learners run the rest.

### What will go wrong, and what to do

| Symptom | Cause | Fix |
|---|---|---|
| `MissingAPIKey` | Colab secret added but toggle off | Sidebar → key icon → **Notebook access ON** → re-run |
| `ModuleNotFoundError: meridian` | bootstrap cell skipped | Run the first cell. It clones the repo in Colab |
| MCP: `Connection closed` | wrong SDK major | `pip install 'mcp>=2,<3'` and restart runtime |
| MCP: `rejected arguments` | stale `mcp` in the runtime | Restart runtime after install |
| NB04 images look wrong | old Pillow | `pip install -U pillow` |
| A guardrail didn't fire | the model complied this time | **This is a teaching moment — see below** |

> **The "it worked this time" moment is a gift, not a failure.** If the model
> happens to comply and a guardrail doesn't fire, say so out loud: *"the control
> didn't need to fire this run — which is exactly why we don't rely on the
> model complying."* Then re-run at `temperature=1.0`.

---

## The spine

Everything hangs off one analogy. Set it up in the first five minutes and
return to it at every block boundary.

> **The model is the doctor. Your system is the hospital.**

| Hospital | Layer | Use this phrase |
|---|---|---|
| Reception | L1 Interface | "checks you're at the right hospital" |
| Triage nurse | L2 Orchestration | "decides who's seen, and when enough is enough" |
| The chart | L3 Context & Prompt | "and who was allowed to write in it" |
| **The doctor** | **L4 Model** | "forms an opinion. That is the whole job" |
| Lab & radiology | L5 Tools | "reports a number, interprets nothing" |
| Attending's signature | L6 Validation | "the institution accepting liability" |
| Medical record | L7 Observability | "so a different doctor, six months later, can tell why" |

---

## Timing

| Time | Block | Notebook | Mode |
|---|---|---|---|
| 0:00–0:05 | Framing + the ER analogy | — | Talk |
| 0:05–0:30 | **Understand the GenAI stack** | 01 | Conceptual |
| 0:30–0:50 | **ML vs GenAI paradigms** | 02 | Conceptual |
| 0:50–1:20 | **System prompting strategies** | 03 | Conceptual + guided |
| 1:20–1:40 | **Multimodal complexity** | 04 | Conceptual |
| 1:40–2:05 | **Protocols & interoperability** | 05 | Conceptual + guided |
| 2:05–2:10 | Wrap-up + the seven sentences | 06 | Talk |

Notebook 06 is **homework**. Do not attempt it live.

### If you are running late

Cut in this order — the first two cost you the least:

1. **NB04's `detail` cost comparison cell** (2 min). Say the number instead:
   *"an image is worth about a thousand tokens."*
2. **NB05's tool-scoping cell** (3 min). State the rule; skip the demo.
3. **NB02's temperature-1.0 run** (4 min). The temp-0 result alone carries the
   argument.
4. **NB03's scaffold comparison** (5 min). Painful to lose, but the injection
   demo is the block's real payload.

**Never cut:** NB01's ablation (guardrails on/off), NB03's quarantine removal,
NB05's one-line registry swap. Those three *are* the session.

---

## Block-by-block

### Block 1 — the GenAI stack (25 min, NB01)

**Open with the Meridian story, not the diagram.** Five failures in a table;
ask the room which are model problems. Let them say "all of them". Then:

> *"Not one of those is a model problem. Every one is a missing component."*

**The beat that lands:** after the naive call, do not evaluate the answer.
Ask the four auditor questions instead — *did it know the policy was lapsed?*
It could not have. Nothing looked it up.

**Watch for:** learners judging the naive output on quality. Redirect: *"it's a
good answer. That's what makes it dangerous."*

**Run the ablation live.** Guardrails on vs off. If the recommendation is the
same both times, use the script above — it strengthens the point.

**The quiz (8 min)** is where the block lands. Pairs, then poll the room. The
pattern to name out loud: **the symptom appears in a different layer from the
defect.**

---

### Block 2 — ML vs GenAI (20 min, NB02)

**The vending machine and the consultant.** Spend a full minute on it. The
punchline: *"you cannot test a consultant by pressing buttons and checking
slots"* — and almost every "GenAI is unreliable" complaint is exactly that
mistake.

**The number that changes minds:** distinct recommendations vs distinct
rationales at temperature 0. Usually the recommendation is stable and the prose
is not. Then say:

> *"Temperature 0 is not a determinism guarantee. It is a greedy decoding
> strategy."*

**The most valuable five minutes of this block** is the rules-engine cell.
Learners expect you to argue for the LLM. Argue for the rules engine instead —
it is faster, free, perfectly reproducible, and it enforces the ceiling
correctly every time. Then show what it cannot do. Land on:

> **Deterministic where a correct answer exists. Probabilistic where judgement
> is required. A hard boundary between them.**

**Expect pushback:** *"so why use a model at all?"* Good question — take it
seriously. The answer is the five bullets in the notebook, especially the
novel-observation one.

---

### Block 3 — prompting as architecture (30 min, NB03) ⭐

**The longest block and the one that changes behaviour on Monday.**

**Read the CLM-4418 injection aloud, slowly.** Then point out what is *not*
there: no "ignore previous instructions", nothing a regex would catch. It reads
like a slightly pushy customer, because that is what real injections look like.

**Sequence the two runs deliberately:**

1. Defended run. Injection fails. Room nods. *Do not move on yet.*
2. Show the actual fence text. The mechanism, not the outcome.
3. Flip `quarantine_untrusted = False`. **One line.**
4. Same injection succeeds.

**Then say the sentence this block exists for:**

> *"The model did not fall for anything. It was handed a document in which the
> ceiling had been lifted, and it read that document correctly. The
> vulnerability was in the assembly, not the model."*

**Then restore guardrails with the broken prompt** and show L6 holding. Defence
in depth: two layers had to fail for money to move.

**The scaffolds section** is lower-energy after that. Frame it as a cost
conversation, not a quality one: at 400 claims/day a 3× token bill is a line
item, so route per claim — and routing lives in L2.

**Exercise question 4 is the one that matters.** Most rooms tier it as T3.
It is untrusted. The tier is decided by **where content entered the system**,
not by how senior the author sounds.

---

### Block 4 — multimodal (20 min, NB04)

**Show the three images before any code.** Give the room 3 minutes to find the
defects themselves. They will find the rear/front contradiction almost
immediately and the smudged digit with prompting.

**Then let the model try.** Whatever it scores, the lesson is the same:

> *"Every one of these was catchable only because the contract had a field for
> it. Take the fields away and ask 'what is the total?' and you get a number.
> Always a number."*

**The spatial-reasoning demo is the crowd-pleaser.** "Which side is damaged?"
three times, then the anchored version three times. Compare *consistency*, not
correctness. The fix for a model-layer weakness was a change in the layer above.

**If the model gets everything right:** say so, then re-run. Variance is the
point, and it is notebook 02 arriving in a new costume.

---

### Block 5 — protocols (25 min, NB05)

**Do the N×M arithmetic on the whiteboard.** 3 apps × 4 tools = 12. Then 3 + 4
= 7. Then add a fifth tool to each side and let them watch the gap widen.

**The kettle.** It does not know where the electricity came from, and that
ignorance is the entire value.

**The demo is the one-line swap.** Build up to it: connect, show discovery
(*"the client source never names these tools"*), call one tool, then swap the
registry into the orchestrator and diff the traces.

> *"You replaced the entire transport and the system above it did not notice.
> That is the definition of a protocol working."*

**Then be honest about the cost.** This matters — MCP is being recommended in a
lot of places where it is wrong. For Meridian today, the in-process registry is
correct. Knowing which situation you are in is the actual skill.

**Mention the stdout trap.** A stray `print()` corrupts the JSON-RPC stream.
Saves somebody an afternoon.

**If MCP fails live:** you have ~4 minutes of buffer. Try a runtime restart
once. If it still fails, fall back to the discovery payload printed in the
learner handout and talk through it — the argument survives without the demo,
though it is weaker. Do not debug in front of the room.

---

## The seven sentences (closing, 5 min)

Put these on screen and read them out. This is what you want retained six
months from now.

1. **The model is the doctor. Your system is the hospital.**
2. **The model proposes. Only your system decides.**
3. **The prompt makes the right behaviour likely; the guardrail makes the wrong behaviour impossible.**
4. **Untrusted content is evidence, never instructions.**
5. **If a correct answer exists, compute it. If judgement is required, generate it — then constrain it.**
6. **A photograph is a second witness, not a judge.**
7. **A hallucination is usually a missing tool.**

---

## Questions you will be asked

**"Can't we just use a bigger model instead of all this?"**
A bigger model makes the doctor better. It does not add a reception desk, a
lab, or an attending signature. Every failure in the Meridian list survives a
model upgrade — and notebook 02's point applies: a stronger model is a
*different* model, and upgrades are breaking changes until your evals say
otherwise.

**"Doesn't LangChain/LangGraph do all this for me?"**
Both of these are true and you need both:
(1) You should not hand-roll orchestration in production — checkpointing,
streaming, retries and observability are solved infrastructure.
(2) A framework will not make a single design decision for you. It will not
choose your tiers, decide what your tool returns when it finds nothing, or
notice that untrusted text is in your system prompt. **The framework abstracts
the mechanics, not the design.** We hand-rolled it here so the mechanics are
visible; W1S2 discusses the production stack.

**"Is prompt injection really solvable?"**
Not in general, and be honest about it. What is achievable is **making it not
matter**: quarantine reduces the rate, guardrails bound the damage, tool scoping
bounds the blast radius, and the trace lets you detect it afterwards. Defence in
depth, not a silver bullet.

**"Our compliance team will never approve an LLM making decisions."**
They are right, and they should not. Show them L6. The model produces a
*recommendation*; deterministic code enforces every rule that must not bend;
a human signs. That is an argument compliance teams accept, because it is the
same shape as every other control they already own.

**"Why not fine-tune it to follow the rules?"**
Fine-tuning changes a probability distribution. The ceiling still isn't
enforced — it is just more likely to be respected. You would be spending money
to move a control from "likely" to "more likely" when a five-line function
moves it to "guaranteed". (Fine-tuning has good uses; this is not one.)

---

## After the session

Learners take notebook 06 away. The lab asks them to **diagram and explain a
complete GenAI system architecture** — the stated outcome of the session.

Ask for the **failure table** specifically when you review their work. It is
the fastest way to tell who understood the layers and who memorised a diagram:
anyone can list seven boxes; only someone who understood them can say where
each one's failure shows up in a trace.
