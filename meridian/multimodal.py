"""
multimodal.py — the complexity multiplier, and the assets that prove it.
========================================================================

WHY this file exists
--------------------
The agenda calls multimodality an *architectural complexity multiplier*. That
word "multiplier" is precise and worth defending in the room.

Adding images does not add one new failure mode. It adds a new failure mode at
**every layer you already had**:

    L1  intake      a 12 MB photo, sideways, with EXIF rotation nobody applied
    L3  prompt      how do three images and two documents get ORDERED and LABELLED?
    L4  model       the model cannot read the smudged digit, and does not say so
    L5  tools       the OCR tool and the vision model disagree about the total
    L6  validation  how do you write a contract test for "looked at the photo"?
    L7  trace       your audit log now contains a photograph of someone's car

And on top of those, one genuinely new class: **cross-modal contradiction.**
The text says front-right. The photo shows rear-left. Neither source is
malfunctioning. Something has to decide, and "the model will notice" is not an
architecture.

THE ANALOGY — a second witness
------------------------------
Teams reach for vision believing a photograph is *evidence* and therefore
settles questions. It is not. A photograph is a **second witness**, and
witnesses:

    - see only what was in frame
    - are confidently wrong about detail
    - and contradict the first witness

A second witness is genuinely valuable. But it does not reduce your
uncertainty automatically — it gives you a second account you now have to
reconcile. Systems that treat images as ground truth are systems that have
promoted a witness to a judge.

WHY THE ASSETS ARE RENDERED, NOT SHIPPED
----------------------------------------
Everything here is drawn at runtime with PIL. Three reasons, and the third is
the real one:

  1. No binary blobs in the repo, no licensing question.
  2. Deterministic — everyone in the room sees the identical artifact.
  3. **The defect is injectable.** The agenda asks for perceptual failure
     modes. A stock photograph contains one only if you are lucky; here the
     smudged `7`, the checkbox straddling two boxes and the text/image
     contradiction are placed deliberately, at known coordinates, so the
     failure reproduces in every run of every session.
"""
from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    _PIL = True
except ModuleNotFoundError:  # pragma: no cover
    _PIL = False


# ---------------------------------------------------------------------------
# The six perceptual failure modes. This taxonomy is the teaching payload of
# notebook 04 — the images exist to make it concrete.
# ---------------------------------------------------------------------------
PERCEPTUAL_FAILURE_MODES: Dict[str, Dict[str, str]] = {
    "resolution_loss": {
        "what": "Detail that mattered is below the model's effective resolution.",
        "example": "A smudged digit in a total: is it Rs 71,200 or Rs 11,200?",
        "why_it_bites": "The model rarely says 'I cannot read this'. It picks one and "
                        "states it in the same confident register as everything else.",
        "control": "Ask for a legibility judgement as a SEPARATE field, and treat "
                   "low legibility as missing evidence rather than as a value.",
    },
    "ambiguity": {
        "what": "The artifact genuinely does not determine the answer.",
        "example": "A tick mark sitting between the 'Total loss' and 'Repairable' boxes.",
        "why_it_bites": "Ambiguity is a property of the DOCUMENT. No model improvement "
                        "fixes it, and a better prompt only hides it.",
        "control": "Make 'ambiguous' a first-class allowed answer in the contract. "
                   "If the enum has no escape hatch, you have forced a guess.",
    },
    "cross_modal_contradiction": {
        "what": "Two modalities assert incompatible facts.",
        "example": "Claimant text says front-right; the photograph shows rear-left.",
        "why_it_bites": "Models are trained to be helpful and coherent, so they tend to "
                        "SYNTHESISE a story that accommodates both instead of flagging it.",
        "control": "Ask for per-source extraction FIRST, reconciliation SECOND. Never "
                   "ask one question that spans two sources.",
    },
    "spatial_reasoning": {
        "what": "Counting, relative position, left/right, and 'which is nearer'.",
        "example": "Which panel is damaged, and is that the driver's side in India?",
        "why_it_bites": "Left/right depends on the observer, and the model does not know "
                        "where the camera was standing.",
        "control": "Anchor to landmarks that do not flip — number plate, fuel flap, "
                   "badge — instead of asking for left or right.",
    },
    "ocr_confusion": {
        "what": "Character-level misreads in rendered or handwritten text.",
        "example": "1/7, 0/O, 5/S, and Indian digit grouping (1,94,000 vs 194,000).",
        "why_it_bites": "A one-character slip moves a payout by an order of magnitude, "
                        "and the output looks completely normal.",
        "control": "Never let a vision model be the sole source of a number that "
                   "matters. Cross-check against a system of record or a second pass.",
    },
    "confident_hallucination": {
        "what": "Details described that are not in the image at all.",
        "example": "A registration number reported for a photo with no plate in frame.",
        "why_it_bites": "It is indistinguishable from correct output by reading alone.",
        "control": "Require a grounding phrase per assertion ('visible in the lower-left "
                   "of the photo'), which makes absence detectable.",
    },
}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _font(size: int = 18, bold: bool = False):
    """Find a usable TrueType font, falling back to PIL's bitmap default.

    Colab has DejaVu; macOS has Helvetica. The fallback is ugly but never
    crashes, and a crashing fixture in a live class is worse than an ugly one.
    """
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
        "/usr/share/fonts/truetype/liberation/LiberationSans%s.ttf" % ("-Bold" if bold else "-Regular"),
        "/System/Library/Fonts/Supplemental/Arial%s.ttf" % (" Bold" if bold else ""),
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _scan_texture(img: "Image.Image", seed: int = 7) -> "Image.Image":
    """Make a clean render look like a phone photo of a printed page.

    Not cosmetic. A pristine 300-dpi render is the easy case, and the easy case
    is not what arrives from a claimant standing in a garage at dusk.
    """
    import random

    rnd = random.Random(seed)
    img = img.rotate(rnd.uniform(-0.8, 0.8), expand=False, fillcolor=(250, 249, 245))
    px = img.load()
    w, h = img.size
    for _ in range(int(w * h * 0.02)):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r, g, b = px[x, y][:3]
        d = rnd.randint(-16, 16)
        px[x, y] = (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)))
    # A soft vignette — uneven lighting, exactly like a hand-held photo.
    overlay = Image.new("L", (w, h), 0)
    od = ImageDraw.Draw(overlay)
    od.ellipse([-w * 0.25, -h * 0.25, w * 1.25, h * 1.25], fill=40)
    img = Image.composite(img, Image.blend(img, Image.new("RGB", (w, h), (215, 212, 205)), 0.25), overlay)
    return img


def to_data_url(img: "Image.Image", fmt: str = "PNG") -> str:
    """Encode for the chat API. Base64 data URLs keep the notebook self-contained."""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/{fmt.lower()};base64,{b64}"


def _require_pil() -> None:
    if not _PIL:
        raise RuntimeError("Pillow is required for the multimodal notebook: pip install pillow")


# ---------------------------------------------------------------------------
# Asset 1 — the claim form. Carries an AMBIGUOUS CHECKBOX on purpose.
# ---------------------------------------------------------------------------

def render_claim_form(
    claim_id: str = "CLM-4419",
    policy_id: str = "POL-88122",
    ambiguous_checkbox: bool = True,
) -> "Image.Image":
    _require_pil()
    W, H = 900, 1150
    img = Image.new("RGB", (W, H), (252, 251, 247))
    d = ImageDraw.Draw(img)

    d.rectangle([40, 40, W - 40, 120], outline=(40, 40, 40), width=2)
    d.text((60, 58), "MERIDIAN INSURANCE", font=_font(26, bold=True), fill=(20, 20, 20))
    d.text((60, 90), "Motor Own-Damage Claim Form  (Form MD-2)", font=_font(15), fill=(60, 60, 60))

    y = 150
    rows = [
        ("Claim reference", claim_id),
        ("Policy number", policy_id),
        ("Date of incident", "09 / 03 / 2026"),
        ("Time of incident", "18:40 hrs"),
        ("Place of incident", "Gachibowli Jn., Hyderabad"),
        ("Vehicle registration", "TS 09 EK 4471"),
    ]
    for label, value in rows:
        d.text((60, y), label, font=_font(15), fill=(90, 90, 90))
        d.line([(300, y + 24), (W - 60, y + 24)], fill=(150, 150, 150), width=1)
        d.text((310, y), value, font=_font(17, bold=True), fill=(15, 15, 15))
        y += 52

    y += 20
    d.text((60, y), "NATURE OF LOSS  (tick one)", font=_font(15, bold=True), fill=(40, 40, 40))
    y += 40
    boxes = [("Repairable damage", 60), ("Total loss", 340), ("Theft", 600)]
    for label, x in boxes:
        d.rectangle([x, y, x + 22, y + 22], outline=(40, 40, 40), width=2)
        d.text((x + 32, y + 2), label, font=_font(15), fill=(30, 30, 30))

    if ambiguous_checkbox:
        # THE PLANTED DEFECT. The tick's vertex sits just OUTSIDE the "Total
        # loss" box and its upstroke crosses into it — so the mark belongs to
        # neither option cleanly. Is it a tick on Total loss placed badly, or a
        # stray mark next to an unticked box?
        #
        # This matters enormously: "repairable" is a Rs 70k claim and "total
        # loss" is a Rs 9L claim. A human assessor would pick up the phone. A
        # model will almost always pick one and report it in the same confident
        # register it uses for the policy number.
        #
        # Note the ambiguity is a property of the DOCUMENT, not the model. No
        # better prompt and no better model removes it — which is exactly why
        # the extraction contract has to allow "ambiguous" as an answer.
        d.line([(322, y + 13), (333, y + 21)], fill=(20, 40, 130), width=3)
        d.line([(333, y + 21), (357, y - 3)], fill=(20, 40, 130), width=3)
    else:
        # The unambiguous control, for the A/B comparison in notebook 04.
        d.line([(64, y + 12), (72, y + 19)], fill=(20, 40, 130), width=3)
        d.line([(72, y + 19), (82, y + 4)], fill=(20, 40, 130), width=3)

    y += 70
    d.text((60, y), "DESCRIPTION OF DAMAGE (in claimant's own words)",
           font=_font(15, bold=True), fill=(40, 40, 40))
    y += 34
    for line in [
        "Another vehicle struck the front-right side at the junction.",
        "Front-right door and wing mirror damaged. No injuries.",
    ]:
        d.text((70, y), line, font=_font(16), fill=(25, 35, 90))
        y += 30

    y += 30
    d.rectangle([60, y, W - 60, y + 130], outline=(120, 120, 120), width=1)
    d.text((75, y + 14), "FOR OFFICE USE ONLY", font=_font(13, bold=True), fill=(120, 120, 120))
    d.text((75, y + 46), "Surveyor assigned:  S. Iyer (Lic. SUR/2019/44281)",
           font=_font(15), fill=(40, 40, 40))
    d.text((75, y + 76), "Estimate received:  Yes", font=_font(15), fill=(40, 40, 40))

    d.text((60, H - 70), "Signature of claimant", font=_font(13), fill=(120, 120, 120))
    d.line([(60, H - 80), (300, H - 80)], fill=(80, 80, 80), width=1)

    return _scan_texture(img, seed=11)


# ---------------------------------------------------------------------------
# Asset 2 — the repair invoice. Carries a SMUDGED DIGIT and a line item that
# contradicts the claimant's description.
# ---------------------------------------------------------------------------

def render_repair_invoice(
    smudge_total: bool = True,
    contradictory_line_item: bool = True,
) -> "Image.Image":
    _require_pil()
    W, H = 900, 1000
    img = Image.new("RGB", (W, H), (255, 254, 250))
    d = ImageDraw.Draw(img)

    d.text((60, 50), "SRI VENKATESWARA AUTO WORKS", font=_font(24, bold=True), fill=(20, 20, 20))
    d.text((60, 84), "Kondapur, Hyderabad 500084   |   GSTIN 36AABCS1429L1ZP",
           font=_font(13), fill=(90, 90, 90))
    d.line([(60, 115), (W - 60, 115)], fill=(60, 60, 60), width=2)

    d.text((60, 135), "TAX INVOICE  No. SVA/2026/0318", font=_font(17, bold=True), fill=(20, 20, 20))
    d.text((60, 165), "Date: 12-03-2026      Vehicle: TS 09 EK 4471", font=_font(15), fill=(50, 50, 50))

    y = 215
    d.rectangle([60, y, W - 60, y + 34], fill=(235, 233, 226))
    for text, x in [("Description", 75), ("Part no.", 430), ("Qty", 600), ("Amount (Rs)", 690)]:
        d.text((x, y + 8), text, font=_font(15, bold=True), fill=(30, 30, 30))
    y += 44

    items: List[Tuple[str, str, str, str]] = [
        ("Door panel - rear left, replace", "DP-RL-338", "1", "24,800"),
        ("Door skin painting, 2 coat", "SVC-PNT-02", "1", "8,400"),
        ("Wing mirror assembly", "WM-L-114", "1", "6,300"),
    ]
    if contradictory_line_item:
        # THE PLANTED CONTRADICTION: a windscreen nobody mentioned, on a claim
        # about a door. This is what a real inflated invoice looks like — not
        # obviously fraudulent, just quietly inconsistent with the story.
        items.append(("Windscreen, laminated, replace", "WS-LAM-07", "1", "18,900"))
    items.extend([
        ("Denting & fitting labour", "SVC-LAB", "6 hr", "7,200"),
        ("Consumables", "SVC-CON", "1", "2,100"),
    ])

    for desc, part, qty, amt in items:
        d.text((75, y), desc, font=_font(15), fill=(25, 25, 25))
        d.text((430, y), part, font=_font(14), fill=(70, 70, 70))
        d.text((610, y), qty, font=_font(15), fill=(25, 25, 25))
        d.text((700, y), amt, font=_font(15), fill=(25, 25, 25))
        d.line([(60, y + 28), (W - 60, y + 28)], fill=(215, 213, 206), width=1)
        y += 40

    y += 20
    d.text((520, y), "Sub-total", font=_font(15), fill=(60, 60, 60))
    d.text((700, y), "67,700", font=_font(15), fill=(25, 25, 25))
    y += 34
    d.text((520, y), "GST @ 18%", font=_font(15), fill=(60, 60, 60))
    d.text((700, y), "12,186", font=_font(15), fill=(25, 25, 25))
    y += 40

    d.rectangle([500, y - 8, W - 60, y + 44], outline=(30, 30, 30), width=2)
    d.text((520, y + 6), "TOTAL", font=_font(19, bold=True), fill=(15, 15, 15))
    total_xy = (690, y + 4)
    d.text(total_xy, "79,886", font=_font(21, bold=True), fill=(15, 15, 15))

    y += 90
    d.text((60, y), "Payment: 50% advance received. Balance on delivery.",
           font=_font(14), fill=(80, 80, 80))
    d.text((60, y + 30), "Authorised signatory", font=_font(13), fill=(120, 120, 120))

    img = _scan_texture(img, seed=23)

    if smudge_total:
        # THE PLANTED DEFECT: blur exactly the leading digit of the total, so
        # 79,886 could be read as 19,886 or 78,886. Everything else stays
        # crisp — which is what makes it a resolution problem rather than a
        # bad-photo problem, and what makes the model's silence so instructive.
        x0, y0 = total_xy[0] - 6, total_xy[1] - 6
        box = (x0, y0, x0 + 34, y0 + 34)
        region = img.crop(box).filter(ImageFilter.GaussianBlur(radius=2.6))
        img.paste(region, box)

    return img


# ---------------------------------------------------------------------------
# Asset 3 — the damage photo (a schematic). Shows REAR-LEFT damage while the
# claimant's text says FRONT-RIGHT.
# ---------------------------------------------------------------------------

def render_damage_photo(damaged_panel: str = "rear-left") -> "Image.Image":
    """A side-profile photo of a car with one quarter panel crumpled.

    DRAW ORDER MATTERS HERE, and for a teaching reason. The landmarks — number
    plate, tail lamp, headlamp, fuel flap — are painted AFTER the damage, so
    they stay visible. Notebook 04 teaches learners to anchor damage
    descriptions to landmarks instead of saying "left" or "right"; an image
    whose landmarks are buried under the damage would quietly undercut the
    exercise it exists to support.
    """
    _require_pil()
    W, H = 1000, 640
    img = Image.new("RGB", (W, H), (176, 186, 196))
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 250], fill=(168, 180, 192))            # sky
    d.rectangle([0, 250, W, H], fill=(105, 105, 108))            # tarmac
    d.rectangle([0, 250, W, 268], fill=(140, 138, 132))          # kerb
    for x in range(60, W, 190):                                  # lane markings
        d.rectangle([x, 560, x + 90, 572], fill=(198, 196, 188))

    # The car, in side profile, FRONT FACING RIGHT.
    body = (58, 82, 122)
    d.polygon([(220, 430), (250, 350), (430, 320), (600, 318), (720, 350), (790, 400),
               (800, 440), (780, 470), (240, 470)], fill=body)
    d.polygon([(300, 350), (430, 330), (430, 396), (296, 396)], fill=(196, 214, 228))
    d.polygon([(448, 330), (580, 330), (580, 396), (448, 396)], fill=(196, 214, 228))
    d.line([(438, 322), (438, 466)], fill=(34, 48, 74), width=4)     # B-pillar
    d.line([(596, 320), (596, 466)], fill=(34, 48, 74), width=3)     # C-pillar

    # ---- the damage, clipped to stay INSIDE the body panel ----------------
    # The quarter panel only — it sits BEHIND the rear window and ABOVE the
    # bumper, so it can be crumpled without painting over either.
    if damaged_panel == "rear-left":
        dx0, dy0, dx1, dy1 = 240, 352, 298, 430
    else:
        dx0, dy0, dx1, dy1 = 702, 352, 782, 430

    d.polygon([(dx0, dy1), (dx0 + 3, dy0 + 14), (dx0 + 22, dy0), (dx0 + 40, dy0 + 20),
               (dx1 - 6, dy0 + 8), (dx1, dy1)], fill=(36, 52, 78))
    for i in range(7):                                                # crease lines
        ox = dx0 + 6 + i * ((dx1 - dx0 - 12) / 7)
        d.line([(ox, dy0 + 16 + (i % 3) * 8), (ox + 8, dy1 - 10 - (i % 4) * 7)],
               fill=(20, 28, 44), width=2)
    d.line([(dx0 + 3, dy0 + 34), (dx1 - 5, dy0 + 56)], fill=(208, 208, 202), width=3)  # bare metal

    # ---- wheels, then LANDMARKS LAST so nothing occludes them -------------
    for cx in (348, 700):
        d.ellipse([cx - 52, 418, cx + 52, 522], fill=(28, 28, 30))
        d.ellipse([cx - 24, 446, cx + 24, 494], fill=(170, 172, 176))

    d.rectangle([788, 390, 810, 414], fill=(240, 232, 190),
                outline=(120, 116, 90), width=1)                  # headlamp -> FRONT
    d.rectangle([222, 384, 240, 410], fill=(190, 60, 52),
                outline=(110, 36, 30), width=1)                   # tail lamp -> REAR
    d.rectangle([226, 434, 318, 460], fill=(238, 238, 234),
                outline=(60, 60, 60), width=2)                    # number plate
    d.text((232, 440), "TS 09 EK 4471", font=_font(14, bold=True), fill=(20, 20, 20))
    d.ellipse([352, 384, 376, 408], outline=(26, 34, 52), width=3)  # fuel flap
    d.line([(356, 396), (372, 396)], fill=(26, 34, 52), width=2)

    d.text((20, 20), "IMG_20260309_1847.jpg", font=_font(15), fill=(240, 240, 240))
    d.text((20, 46), "09/03/2026 18:47", font=_font(14), fill=(230, 230, 230))

    return _scan_texture(img, seed=31)


# ---------------------------------------------------------------------------
# The structured multimodal envelope — the part that is ARCHITECTURE.
# ---------------------------------------------------------------------------

@dataclass
class Asset:
    """One piece of evidence, with the metadata that makes it reasonable about.

    `provenance` and `trust` are the fields teams forget, and they are the ones
    that matter. A garage invoice and a claimant's phone photo are not equally
    authoritative, and if that difference is not in the prompt then the model
    is weighing them equally — which is a decision you made by accident.
    """

    label: str
    kind: str            # "image" | "text"
    provenance: str      # who produced it
    trust: str           # "verified" | "claimant-supplied" | "third-party"
    content: Any         # PIL Image, or str
    # What we want extracted from THIS source specifically. Asking one broad
    # question across five assets is how you get a confident average of five
    # different documents.
    asks: List[str] = field(default_factory=list)


def build_multimodal_messages(
    system_prompt: str,
    assets: List[Asset],
    instruction: str,
    detail: str = "high",
) -> List[Dict[str, Any]]:
    """Assemble a multimodal turn with per-asset labelling and provenance.

    THE RULE THIS ENCODES: *a model cannot reason about the relationship
    between two images it was never told apart.* Most multimodal bugs are not
    perception failures at all — they are the model doing its best with a bag
    of unlabelled pixels it was handed in an arbitrary order.

    So every asset gets, in this order:
        1. a text preamble naming it, its source and its trust level
        2. then the image itself

    The preamble goes BEFORE the image because the model reads the sequence in
    order, and context that arrives after the evidence is context that was not
    available while looking at it.
    """
    content: List[Dict[str, Any]] = []

    content.append({
        "type": "text",
        "text": (
            f"You are given {len(assets)} pieces of evidence. They are labelled and "
            "each carries a provenance and a trust level. Evidence marked "
            "'claimant-supplied' is an account, not a verified fact.\n\n"
            "Extract from EACH source independently before comparing them. Do not "
            "reconcile contradictions by inventing a story that fits both — report "
            "the contradiction."
        ),
    })

    for i, asset in enumerate(assets, 1):
        header = (
            f"\n--- EVIDENCE {i}: {asset.label} ---\n"
            f"source: {asset.provenance}\n"
            f"trust: {asset.trust}\n"
        )
        if asset.asks:
            header += "extract specifically: " + "; ".join(asset.asks) + "\n"
        content.append({"type": "text", "text": header})

        if asset.kind == "image":
            content.append({
                "type": "image_url",
                "image_url": {"url": to_data_url(asset.content), "detail": detail},
            })
        else:
            content.append({"type": "text", "text": str(asset.content)})

    content.append({"type": "text", "text": "\n" + instruction})

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]


# The extraction contract for notebook 04. Per-source first, reconciliation
# second — the shape is the control.
MULTIMODAL_EXTRACTION_CONTRACT = """Return a single JSON object and nothing else:
{
  "per_source": [
    {
      "evidence": string,            // the label you were given
      "damaged_area": string | null, // anchored to a landmark, not left/right
      "amounts_seen": [string],      // exactly as printed, including separators
      "legibility": "CLEAR" | "PARTIAL" | "ILLEGIBLE",
      "illegible_fields": [string],  // name anything you could not read
      "grounding": string            // WHERE in the source you saw this
    }
  ],
  "contradictions": [
    { "between": [string, string], "description": string, "which_to_trust": string }
  ],
  "resolved_view": {
    "damaged_area": string | null,
    "assessed_amount_inr": number | null,
    "confidence": "HIGH" | "MEDIUM" | "LOW"
  },
  "cannot_determine": [string]       // questions the evidence does not answer
}"""


MULTIMODAL_SYSTEM_PROMPT = (
    "You are the perception component of Meridian Insurance's claims-triage "
    "system. Your job is to EXTRACT what each piece of evidence actually shows "
    "and to REPORT disagreement between sources.\n\n"
    "You are not the decision-maker. Do not recommend approve, refer or decline.\n\n"
    "Rules:\n"
    "- If you cannot read something, say ILLEGIBLE. A guess recorded as a fact "
    "is the single most damaging thing you can do here.\n"
    "- Describe damage by anchoring to fixed landmarks visible in the image "
    "(number plate, fuel flap, tail lamp, headlamp) rather than 'left' or "
    "'right', which depend on where the camera was standing.\n"
    "- Report amounts exactly as printed, including separators, before "
    "interpreting them.\n"
    "- Contradictions between sources are the most valuable thing you can find. "
    "Never smooth them over."
)
