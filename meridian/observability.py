"""
observability.py — L7, Observability & Governance. The medical record.
======================================================================

WHY this file exists
--------------------
In a traditional ML system, when something goes wrong you have an input, a
model version and an output. Three things. You can reproduce the failure on
your laptop.

In a GenAI system, "something went wrong" might mean:

    the prompt hierarchy changed last Tuesday
    ... so the model chose a different tool
    ... which returned a not-found
    ... which it silently ignored
    ... and it answered from parametric memory instead
    ... fluently, confidently, and wrongly.

Not one of those steps is visible in the output. The output is a paragraph that
reads perfectly well. **Without a trace, this system is not debuggable — it is
merely observable in the sense that you can watch it fail.**

That is why L7 is a layer and not a logging statement. And it is why the
recurring question all session is:

    *"What does this step look like when it goes wrong —
      and where would you see it in the trace?"*

WHAT A GENAI TRACE MUST CARRY THAT AN ML LOG DOES NOT
-----------------------------------------------------
    prompt fingerprint   which version of the instructions governed this run
    tool calls + results the model's reach into the world, and what came back
    token counts + cost  because a design change can triple your bill silently
    guardrail firings    what the system refused to let the model do
    latency per step     since the slow step is almost never the one you think

THE ANALOGY
-----------
A hospital's medical record is not there to help the doctor remember. It is
there so that a *different* doctor, six months later, can reconstruct why a
decision was made — and so the hospital can answer a coroner. Your trace has
exactly the same two jobs: debugging, and accountability.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Span:
    """One step. The layer that produced it is a first-class field.

    Recording the layer is what turns a log into an architecture diagram you
    can query: "show me every run where L6 blocked something L4 proposed."
    """

    name: str
    layer: str
    started_at: float = field(default_factory=time.time)
    duration_ms: int = 0
    attributes: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def finish(self, **attributes: Any) -> "Span":
        self.duration_ms = int((time.time() - self.started_at) * 1000)
        self.attributes.update(attributes)
        return self


@dataclass
class Trace:
    """Everything that happened in one run of the system."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    claim_id: str = ""
    prompt_fingerprint: str = ""
    model: str = ""
    spans: List[Span] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    # -- recording ----------------------------------------------------------

    def span(self, name: str, layer: str, **attributes: Any) -> Span:
        s = Span(name=name, layer=layer, attributes=dict(attributes))
        self.spans.append(s)
        return s

    def record(self, name: str, layer: str, **attributes: Any) -> Span:
        """An instantaneous event — no duration to measure."""
        return self.span(name, layer, **attributes).finish()

    # -- aggregates ---------------------------------------------------------

    @property
    def total_tokens(self) -> int:
        return sum(int(s.attributes.get("total_tokens", 0)) for s in self.spans)

    @property
    def total_cost_usd(self) -> float:
        return sum(float(s.attributes.get("cost_usd", 0.0)) for s in self.spans)

    @property
    def total_ms(self) -> int:
        return int((time.time() - self.started_at) * 1000)

    @property
    def model_calls(self) -> int:
        return sum(1 for s in self.spans if s.layer == "L4")

    @property
    def tool_calls(self) -> List[str]:
        return [str(s.attributes.get("tool")) for s in self.spans
                if s.layer == "L5" and s.attributes.get("tool")]

    @property
    def guardrails_fired(self) -> List[str]:
        out: List[str] = []
        for s in self.spans:
            if s.layer == "L6":
                out.extend(s.attributes.get("violations", []) or [])
        return out

    # -- display ------------------------------------------------------------

    def render(self, width: int = 92) -> str:
        """A readable trace for a notebook cell. This is the debugging UI."""
        lines = [
            "=" * width,
            f"TRACE {self.run_id}   claim={self.claim_id or '-'}   model={self.model or '-'}",
            f"prompt fingerprint: {self.prompt_fingerprint or '-'}",
            "=" * width,
        ]
        for i, s in enumerate(self.spans, 1):
            flag = " !!" if s.error else ""
            lines.append(f"{i:>2}. [{s.layer}] {s.name:<34} {s.duration_ms:>6} ms{flag}")
            for k, v in s.attributes.items():
                if k in ("violations",) and not v:
                    continue
                text = json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else str(v)
                if len(text) > width - 12:
                    text = text[: width - 15] + "..."
                lines.append(f"      {k}: {text}")
            if s.error:
                lines.append(f"      error: {s.error}")
        lines.append("-" * width)
        lines.append(
            f"total {self.total_ms} ms   |   {self.model_calls} model call(s)   |   "
            f"{self.total_tokens} tokens   |   ${self.total_cost_usd:.5f}"
        )
        if self.tool_calls:
            lines.append(f"tools called: {', '.join(self.tool_calls)}")
        if self.guardrails_fired:
            lines.append("guardrails fired:")
            lines.extend(f"   - {v}" for v in self.guardrails_fired)
        lines.append("=" * width)
        return "\n".join(lines)

    def to_audit_record(self) -> Dict[str, Any]:
        """What governance keeps. Note what is NOT here: raw claimant content.

        Retaining the full prompt would mean retaining personal data in your
        logging system indefinitely, which is a DPDP problem wearing an
        observability costume. Keep the fingerprint and the decisions; keep the
        payload only where policy says you may.
        """
        return {
            "run_id": self.run_id,
            "claim_id": self.claim_id,
            "prompt_fingerprint": self.prompt_fingerprint,
            "model": self.model,
            "steps": [
                {"layer": s.layer, "name": s.name, "ms": s.duration_ms,
                 "error": s.error} for s in self.spans
            ],
            "tools_called": self.tool_calls,
            "guardrails_fired": self.guardrails_fired,
            "tokens": self.total_tokens,
            "cost_usd": round(self.total_cost_usd, 6),
            "latency_ms": self.total_ms,
        }


def compare(a: Trace, b: Trace, width: int = 92) -> str:
    """Diff two runs. The single most useful debugging move in GenAI.

    "It worked yesterday" is answerable only if you can put yesterday's trace
    next to today's and look at the four things that actually differ.
    """
    rows = [
        ("run", a.run_id, b.run_id),
        ("prompt fingerprint", a.prompt_fingerprint, b.prompt_fingerprint),
        ("model", a.model, b.model),
        ("model calls", a.model_calls, b.model_calls),
        ("tools", ", ".join(a.tool_calls) or "-", ", ".join(b.tool_calls) or "-"),
        ("tokens", a.total_tokens, b.total_tokens),
        ("cost usd", f"{a.total_cost_usd:.5f}", f"{b.total_cost_usd:.5f}"),
        ("guardrails", len(a.guardrails_fired), len(b.guardrails_fired)),
    ]
    out = ["=" * width, f"{'':<20}{'RUN A':<34}{'RUN B':<34}", "-" * width]
    for label, x, y in rows:
        mark = "  " if str(x) == str(y) else "* "
        out.append(f"{mark}{label:<18}{str(x):<34}{str(y):<34}")
    out.append("=" * width)
    out.append("* marks a difference — start your debugging at the topmost one.")
    return "\n".join(out)
