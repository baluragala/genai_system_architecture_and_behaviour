"""Notebook 04 — Analyse multimodal complexity (20 min)."""
from __future__ import annotations

from nbtools import code, md, predict, standard_opening

FILE = "04_multimodal.ipynb"


def build():
    c = standard_opening(
        FILE,
        title="Notebook 04 — Multimodality as a Complexity Multiplier",
        subtitle=(
            "Three pieces of evidence that disagree with each other, and a model that "
            "would very much like to tell you a story in which they all agree."
        ),
        duration="20 min",
        mode="Conceptual + Guided Analysis",
        where="**L1**, **L3** and **L4** — intake, how evidence is assembled, and what perception actually returns.",
        takeaway=(
            "**A photograph is a second witness, not a judge.** Adding a modality does not "
            "add truth — it adds another account you now have to reconcile, and a new "
            "failure mode at every layer you already had."
        ),
    )

    c += [
        md('''
---

## WHY — "just send the photo to the model"

Meridian's next sprint is obvious. Claims arrive with photographs; the model
can see; send it the photograph.

It demos beautifully. It is also the point at which a well-behaved system
starts producing failures nobody on the team has a name for.

### The word "multiplier" is doing real work

Multimodality does not add *one* new failure mode. It adds a failure mode at
**every layer you already had**:

| Layer | The new failure |
|---|---|
| **L1** intake | A 12 MB photo, sideways, with EXIF rotation nobody applied |
| **L3** prompt | Three images and two documents — in what *order*, with what *labels*? |
| **L4** model | It cannot read the smudged digit, and does not mention this |
| **L5** tools | The OCR tool and the vision model disagree about the total |
| **L6** validation | How do you write a contract test for "actually looked at the photo"? |
| **L7** trace | Your audit log now contains photographs of people's vehicles |

And on top of those, one genuinely new class: **cross-modal contradiction.**
The text says front-right. The photo shows rear-left. Neither source is
malfunctioning. Something has to decide, and *"the model will notice"* is not
an architecture.

### The analogy — a second witness

Teams reach for vision believing a photograph is **evidence**, and therefore
settles questions. It is not. A photograph is a **second witness**, and
witnesses:

- see only what was in frame,
- are confidently wrong about detail,
- and contradict the first witness.

A second witness is genuinely valuable. But it does not reduce your uncertainty
automatically — it gives you a second account to reconcile.

> **Systems that treat images as ground truth have promoted a witness to a judge.**
'''),

        md('''
## The evidence for CLM-4419

Three artifacts, rendered deterministically so everyone in this room sees the
identical pixels. Each carries a **planted defect** — because the agenda asks
for perceptual failure modes, and a stock photograph contains one only if you
are lucky.
'''),

        code('''
# ============================================================
# THE EVIDENCE — rendered, so the defects are reproducible
# ============================================================
from meridian.multimodal import (render_claim_form, render_repair_invoice,
                                 render_damage_photo)
from meridian import data as records
from IPython.display import display

claim = records.get_claim("CLM-4419")
print(records.claim_brief("CLM-4419"))
print()
print("CLAIMANT'S ACCOUNT (text):")
print(claim.claimant_statement)

form    = render_claim_form()
invoice = render_repair_invoice()
photo   = render_damage_photo()

print("\\nrendered:", form.size, invoice.size, photo.size)
'''),

        code('''
display(photo.resize((700, 448)))
print("EVIDENCE 1 — the damage photograph (claimant-supplied)")
'''),

        code('''
display(invoice.resize((640, 711)))
print("EVIDENCE 2 — the repair invoice (third-party: the garage)")
'''),

        code('''
display(form.resize((600, 767)))
print("EVIDENCE 3 — the claim form (claimant-supplied)")
'''),

        md('''
### Find the defects yourself, before the model does (3 min)

Look at the three images above and answer:

1. **Where is the damage** in the photograph — front or rear? What does the
   claimant's *text* say?
2. Read the **TOTAL** on the invoice. Are you certain of the first digit?
3. Which box is ticked under **NATURE OF LOSS**?
4. Is there a line item on the invoice that has nothing to do with the described damage?

Hold your answers. Now let's see what the model reports.
'''),

        predict("The model is about to see all three. Which of these four will it report: the cross-modal contradiction, the illegible digit, the ambiguous checkbox, the irrelevant line item? Which do you think it will silently smooth over?"),

        code('''
# ============================================================
# THE STRUCTURED MULTIMODAL ENVELOPE — the part that is ARCHITECTURE
# ============================================================
from meridian.multimodal import (Asset, build_multimodal_messages,
                                 MULTIMODAL_SYSTEM_PROMPT,
                                 MULTIMODAL_EXTRACTION_CONTRACT)

assets = [
    Asset(label="Damage photograph", kind="image",
          provenance="claimant's mobile phone, 09/03/2026 18:47",
          trust="claimant-supplied",
          content=photo,
          asks=["which panel is damaged, anchored to a visible landmark",
                "any visible registration number"]),
    Asset(label="Repair invoice", kind="image",
          provenance="Sri Venkateswara Auto Works (garage)",
          trust="third-party",
          content=invoice,
          asks=["the TOTAL exactly as printed", "every line item description"]),
    Asset(label="Claim form MD-2", kind="image",
          provenance="claimant, submitted at intake",
          trust="claimant-supplied",
          content=form,
          asks=["which NATURE OF LOSS box is ticked",
                "the description of damage in the claimant's words"]),
    Asset(label="Claimant's written account", kind="text",
          provenance="claim intake system, free-text field",
          trust="claimant-supplied",
          content=claim.claimant_statement),
]

messages = build_multimodal_messages(
    system_prompt=MULTIMODAL_SYSTEM_PROMPT,
    assets=assets,
    instruction=MULTIMODAL_EXTRACTION_CONTRACT,
)

print(f"{len(assets)} assets -> {len(messages[1]['content'])} content parts")
print("part types:", [p["type"] for p in messages[1]["content"]])
'''),

        md('''
### Read the envelope structure before you run it

Every asset gets, **in this order**:

1. a text preamble naming it, its **provenance** and its **trust level**,
2. then the image itself.

Two decisions there are load-bearing:

**The preamble goes *before* the image.** The model reads the sequence in
order. Context arriving after the evidence is context that was not available
while looking at it.

**`provenance` and `trust` are fields teams forget** — and they are the ones
that matter. A garage's invoice and a claimant's phone photo are not equally
authoritative. If that difference is not in the prompt, the model is weighing
them equally, and **you made that decision by accident.**

> **A model cannot reason about the relationship between two images it was
> never told apart.** Most "multimodal bugs" are not perception failures at
> all — they are a model doing its best with a bag of unlabelled pixels handed
> over in arbitrary order.
'''),

        code('''
import json
from meridian import get_llm, extract_json

vision = get_llm()
out = vision.complete(messages, max_tokens=1800)

print(f"[{out.total_tokens} tokens, ${out.cost_usd:.5f}, {out.latency_ms} ms]")
print()
report = extract_json(out.text)
print(json.dumps(report, indent=2, ensure_ascii=False))
'''),

        code('''
# ============================================================
# SCORE IT — did the model find the four planted defects?
# ============================================================
blob = json.dumps(report).lower()

checks = {
    "cross-modal contradiction (text says front, photo shows rear)":
        any(k in blob for k in ["contradict", "rear", "inconsist", "discrep"]),
    "illegible / uncertain digit in the invoice TOTAL":
        any(k in blob for k in ["illegible", "partial", "unclear", "smudg", "cannot"]),
    "ambiguous NATURE OF LOSS checkbox":
        any(k in blob for k in ["ambig", "unclear", "between", "straddl"]),
    "windscreen line item unrelated to the described damage":
        "windscreen" in blob or "windshield" in blob,
}

for label, found in checks.items():
    print(f"  [{'FOUND' if found else ' --- '}]  {label}")

print()
print("contradictions reported:", len(report.get("contradictions", [])))
print("cannot_determine        :", report.get("cannot_determine"))
print("resolved confidence     :", report.get("resolved_view", {}).get("confidence"))
'''),

        md('''
### Whatever it found, the architectural lesson is the same

Run this two or three times. You will see the score move between runs — which
is notebook 02's point arriving in a new costume.

The important observation is not *how many* it caught. It is:

> **Every one of these was catchable only because the contract had a field for it.**

- It can report an illegible digit only because `legibility` and
  `illegible_fields` exist as fields.
- It can report a contradiction only because `contradictions` is a top-level
  array, extracted **per-source first**, reconciliation second.
- It can decline to answer only because `cannot_determine` exists.

Take those fields away and ask *"what is the total?"* and you get a number.
Always a number. **A contract with no escape hatch forces a guess** — and the
guess arrives in the same confident register as everything the model got right.
'''),

        md('''
---

## The six perceptual failure modes

The taxonomy this notebook exists to teach. For each: what it is, why it bites,
and the *architectural* control — not "write a better prompt".
'''),

        code('''
from meridian.multimodal import PERCEPTUAL_FAILURE_MODES

for i, (name, spec) in enumerate(PERCEPTUAL_FAILURE_MODES.items(), 1):
    print(f"{i}. {name.upper().replace('_', ' ')}")
    print(f"   what        : {spec['what']}")
    print(f"   example     : {spec['example']}")
    print(f"   why it bites: {spec['why_it_bites']}")
    print(f"   CONTROL     : {spec['control']}")
    print()
'''),

        md('''
### The one everybody underestimates: spatial reasoning

Ask a model *"is the damage on the left or the right?"* and it will answer.
Confidently. About half the time.

Not because vision models are bad at left and right — because **the question is
underdetermined.** Left of what? The camera was standing somewhere, and the
model does not know where. In a right-hand-drive market, "driver's side" flips
the answer again.

The control is not a better model. It is **a better question**:

> ❌ "Which side is damaged?"
> ✅ "Which panel is damaged, relative to the number plate and the fuel flap?"

Landmarks don't flip. Let's prove it costs nothing to ask properly.
'''),

        code('''
# ============================================================
# THE SAME IMAGE, TWO QUESTIONS
# ============================================================
from meridian.multimodal import to_data_url

def ask_photo(question: str, n: int = 3):
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": question},
        {"type": "image_url",
         "image_url": {"url": to_data_url(photo), "detail": "high"}},
    ]}]
    return [get_llm(temperature=0.7).complete(msgs, max_tokens=120).text.strip()
            for _ in range(n)]

print("UNDERDETERMINED — 'which side?'")
for i, a in enumerate(ask_photo(
        "Which side of this car is damaged? Answer in one short sentence."), 1):
    print(f"  {i}. {a}")

print()
print("ANCHORED — 'relative to which landmark?'")
for i, a in enumerate(ask_photo(
        "Looking at this car: is the damaged panel NEARER to the red tail lamp "
        "and the number plate, or NEARER to the pale headlamp? Answer in one "
        "short sentence naming the landmark you used."), 1):
    print(f"  {i}. {a}")
'''),

        md('''
Compare the *consistency* of the two sets, not just their correctness.

The anchored question is usually both more stable and more useful downstream —
*"nearer the tail lamp"* survives the photo being flipped, the camera moving,
and the market being right-hand-drive. **"Left" does not.**

This is a prompt-layer control (L3) for a perception problem (L4), which is
worth pausing on: the fix for a model-layer weakness was to change what the
layer above it asked for.
'''),

        md('''
---

## What this costs, and the L1 decision nobody makes on purpose

Images are not free, and the cost is not obvious from the code.
'''),

        code('''
# ============================================================
# THE COST OF PERCEPTION — and the `detail` parameter
# ============================================================
question = "In one sentence: what is the TOTAL amount printed on this invoice?"

for detail in ["low", "high"]:
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": question},
        {"type": "image_url",
         "image_url": {"url": to_data_url(invoice), "detail": detail}},
    ]}]
    r = get_llm().complete(msgs, max_tokens=120)
    print(f"detail={detail:<5} {r.prompt_tokens:>6} prompt tokens  "
          f"${r.cost_usd:.5f}  {r.latency_ms:>5} ms")
    print(f"             -> {r.text.strip()[:110]}")
    print()

text_only = get_llm().complete(
    [{"role": "user", "content": "Say OK."}], max_tokens=10)
print(f"text-only baseline: {text_only.prompt_tokens} prompt tokens")
print()
print("An image is worth roughly a thousand tokens. At 400 claims/day with")
print("three images each, `detail` is a budget decision -- and a decision")
print("about whether the smudged digit is readable at all.")
'''),

        md('''
### The intake rules this implies (L1)

Every one of these is a decision your system makes whether you make it
deliberately or not:

| Decision | Sane default | What happens if you skip it |
|---|---|---|
| Max upload size | 5 MB | A 14 MB photo, a 30-second timeout, a confused user |
| Downscale before sending | Longest edge ≤ 1568 px | You pay for pixels the model discards |
| EXIF rotation | Apply at intake | The model reasons about a sideways car |
| `detail` level | `high` only when text must be read | 3× your bill, or an unreadable total |
| Strip metadata | Yes — GPS is in there | Location data in your logs, and a DPDP finding |
| Reject non-images | Yes | Someone uploads a 200-page PDF |

The last two are not performance items. They are **governance** items that
happen to live at the door.
'''),

        md('''
---

## Exercise — design the intake contract (5 min)

Meridian wants to accept **video** walkarounds of damaged vehicles.

In pairs, answer for each layer:

1. **L1** — what does intake enforce? (size, duration, format, frame rate)
2. **L3** — how do you present a video to a model that takes images? How many
   frames, chosen how, labelled how?
3. **L4** — which of the six failure modes get *worse* with video? Which get better?
4. **L6** — what does the output contract need that the photo contract didn't?
5. **L7** — you are now storing video of people's homes and vehicles. What
   changes in retention?

<details>
<summary>Discussion notes</summary>

**L1** — duration cap (30 s), server-side frame extraction, reject audio tracks
(you almost certainly don't want to process speech you didn't plan for).

**L3** — sample frames deterministically (e.g. 1 fps, or scene-change
detection), and **label each frame with its timestamp**. Unlabelled frames are
the bag-of-pixels problem again, now with a temporal dimension.

**L4** — *spatial reasoning gets better*: multiple angles disambiguate what one
photo cannot. *Confident hallucination gets worse*: more frames, more surface
for invented detail. *Cost multiplies by frame count*, which is the real
constraint.

**L6** — you now need **temporal consistency**: does the damage appear in the
same place across frames? A contradiction *between frames of one video* is a
strong fraud signal and a new contract field.

**L7** — video is far more identifying than a photo: faces, house interiors,
neighbours, number plates of uninvolved vehicles. Retention has to shorten, and
"we keep the whole payload in the trace" stops being defensible.
</details>
'''),

        md('''
---

## Where we are, and what's next

You gave a model three contradictory artifacts and watched what it did with
them — and, more importantly, saw that what it *could* report was bounded by
the fields you gave it.

**The takeaway again:**
> **A photograph is a second witness, not a judge.** Multimodality multiplies
> the failure modes of every layer you already had, and adds one of its own.

Next, the last block: how a GenAI system reaches tools it does not own, and
why that needs a **protocol**. Notebook 05, 25 minutes.

### Before you move on
- [ ] Can you name the six perceptual failure modes and one control for each?
- [ ] Why does per-source-first extraction beat one question spanning all sources?
- [ ] Why is "which side is damaged?" the wrong question, architecturally?
- [ ] Which intake rules are performance decisions, and which are governance decisions?
'''),
    ]
    return c
