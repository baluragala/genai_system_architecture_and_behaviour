"""
config.py — the ONLY module in this package that knows OpenAI exists.
=====================================================================

WHY this file exists
--------------------
Every other module in `meridian` is written against one small interface:

    llm.complete(messages, tools=None, schema=None) -> Completion

Nothing else imports `openai`. That is not fussiness — it is the first
architectural lesson of the session, made physical:

    **The model is a replaceable component behind an interface.**

If swapping GPT-4o-mini for Claude or Gemini or a fine-tuned Llama means
editing eleven files, you did not build a GenAI *system*. You built an
application with a vendor welded into its spine. Here it means writing one
adapter class, and the layers above never notice.

THE STACK
---------
**OpenAI, with native tool calling and vision. An API key is required.**

There is deliberately no offline fallback. A simulated model can show you the
*shape* of a layered system while quietly misrepresenting the one property the
whole session is about: that this component is **probabilistic**. Notebook 02
runs the same claim ten times and counts how often the system disagrees with
itself. A stub would answer identically every time and teach you a comfortable
lie.

    Colab : sidebar -> key icon -> add OPENAI_API_KEY -> Notebook access ON
    local : export OPENAI_API_KEY=sk-...

TEMPERATURE
-----------
Default 0. Not because 0 is "correct", but because a classroom needs a
controlled variable — notebook 02 raises it on purpose and the contrast is the
lesson. In production, temperature is a product decision, not a default.

THE ER ANALOGY
--------------
This module is **the doctor**. One person, one skill: look at the chart, form
an opinion. The doctor does not admit patients, does not run the lab, does not
sign the discharge paperwork and does not keep the medical record. Every one of
those is a different layer, and confusing them is how hospitals — and GenAI
systems — hurt people.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------
# Defaults. Overridable by environment so an instructor can switch the whole
# session to a different model with one variable.
# --------------------------------------------------------------------------
DEFAULT_MODEL = os.getenv("MERIDIAN_MODEL", "gpt-4o-mini")
DEFAULT_TEMPERATURE = float(os.getenv("MERIDIAN_TEMPERATURE", "0"))

# Rough public pricing (USD per 1M tokens) for gpt-4o-mini, used so that the
# observability layer can show a cost column. Cost is an architectural concern:
# a design that triples token count is a design decision, and you should be
# able to see it in the trace rather than in next month's invoice.
PRICE_PER_1M = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o": {"in": 2.50, "out": 10.00},
}


class MissingAPIKey(RuntimeError):
    """Raised with instructions rather than a stack trace."""


def load_api_key() -> str:
    """Find OPENAI_API_KEY in env, then Colab Secrets. Fail loudly otherwise.

    Deliberately does NOT prompt interactively: a `getpass` box in a shared
    classroom screen-share is how keys leak.
    """
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key

    try:  # Colab Secrets — the supported path for this session
        from google.colab import userdata  # type: ignore

        key = userdata.get("OPENAI_API_KEY")
        if key:
            os.environ["OPENAI_API_KEY"] = key
            return key
    except Exception:
        pass

    raise MissingAPIKey(
        "OPENAI_API_KEY is not set — these notebooks call a real model.\n"
        "\n"
        "  Colab : sidebar -> key icon -> add a secret named OPENAI_API_KEY\n"
        "          -> toggle 'Notebook access' ON -> re-run this cell\n"
        "  local : export OPENAI_API_KEY=sk-...   then restart the kernel\n"
        "\n"
        "There is no offline fallback, on purpose. See meridian/config.py."
    )


@dataclass
class ToolCall:
    """One request from the model to run a tool. Provider-neutral on purpose."""

    id: str
    name: str
    arguments: Dict[str, Any]

    def __repr__(self) -> str:  # pragma: no cover - display only
        return f"ToolCall({self.name}, {json.dumps(self.arguments, ensure_ascii=False)})"


@dataclass
class Completion:
    """What the Model layer hands back — and nothing more.

    Note what is NOT here: no decision, no approval, no payout. The model
    returns *text and intentions*. Turning that into a decision is L6's job,
    and keeping those separate is the difference between a system you can
    audit and one you can only apologise for.
    """

    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = DEFAULT_MODEL
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    raw: Any = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        p = PRICE_PER_1M.get(self.model.split(":")[0], PRICE_PER_1M["gpt-4o-mini"])
        return (self.prompt_tokens * p["in"] + self.completion_tokens * p["out"]) / 1_000_000

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLM:
    """The Model layer (L4). A thin, honest adapter — no business logic.

    Every method returns a `Completion`. It never raises on a *model* problem
    it can describe; it raises only on programmer error and transport failure,
    because a layer that swallows its own errors is a layer you cannot debug.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        seed: Optional[int] = None,
    ) -> None:
        load_api_key()
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("pip install openai>=1.30") from exc

        self._client = OpenAI()
        self.model = model
        self.temperature = temperature
        # `seed` is best-effort on OpenAI's side. Notebook 02 uses it to show
        # that even *with* a seed, determinism is not contractual — which is
        # precisely the paradigm shift the agenda asks us to teach.
        self.seed = seed

    @property
    def name(self) -> str:
        return f"openai:{self.model}@T={self.temperature}"

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 1200,
    ) -> Completion:
        """One inference call.

        `messages`     already-assembled chat messages (L3 built these)
        `tools`        OpenAI-shape tool schemas (L5 owns these)
        `schema`       a JSON Schema to force structured output (L6 owns this)
        """
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "strict": True, "schema": schema},
            }
        if self.seed is not None:
            kwargs["seed"] = self.seed

        started = time.perf_counter()
        resp = self._client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)

        choice = resp.choices[0]
        msg = choice.message

        calls: List[ToolCall] = []
        for tc in getattr(msg, "tool_calls", None) or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                # The model emitted malformed JSON for its own tool call. This
                # happens, it is not exotic, and a system that assumes it never
                # happens will crash in production at 2am. Surface it as data.
                args = {"__malformed__": tc.function.arguments}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        usage = getattr(resp, "usage", None)
        return Completion(
            text=msg.content or "",
            tool_calls=calls,
            finish_reason=choice.finish_reason or "stop",
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
            raw=resp,
        )


_default: Optional[LLM] = None


def get_llm(**kwargs: Any) -> LLM:
    """Module-level singleton so notebooks do not build five clients.

    Pass any kwarg (e.g. `temperature=1.0`) to get a fresh, independent client
    instead of the shared one.
    """
    global _default
    if kwargs:
        return LLM(**kwargs)
    if _default is None:
        _default = LLM()
    return _default


def current_config() -> Dict[str, Any]:
    """A one-line environment report for the top of every notebook."""
    return {
        "model": DEFAULT_MODEL,
        "temperature": DEFAULT_TEMPERATURE,
        "api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "in_colab": "google.colab" in __import__("sys").modules,
    }
