"""Part D — multimodal, MCP, end-to-end, failure modes, hardening, capstone."""
from __future__ import annotations

from copilot_common import analogy, breaks, code, how, md, predict, what, why


def build():
    return [
        # ================================================================
        md("---\n\n# 18. Multimodal — a second, unreliable witness"),

        why('''
An employee attaches a screenshot: *"VPN shows this after the laptop update."*

Sending it to a vision model is one line, and it demos beautifully. It is also
the point at which a well-behaved system starts producing failures your team has
no name for.

The word usually used is *multimodal*. The word that predicts your incidents is
**multiplier**.
'''),

        analogy('''
Aviation has a specific, well-studied killer: **spatial disorientation.** The
pilot looks out of the window, forms a confident belief about which way is up,
and it is wrong. Experienced crews have flown perfectly serviceable aircraft
into the ground while certain they were straight and level.

The fix was never "look harder". It was **instruments, and a rule: when the
window and the instruments disagree, trust the instruments.**

A screenshot is the window. It is genuinely useful and it is not ground truth.

> **A photograph is a second witness, not a judge.**
'''),

        what('''
Adding images does not add *one* failure mode. It adds one at **every layer you
already had**:

| Layer | The new failure |
|---|---|
| **L1** intake | a 12 MB screenshot, sideways, EXIF rotation nobody applied |
| **L3** prompt | three images and two documents — in what *order*, with what *labels*? |
| **L4** model | it cannot read the blurred error code, and does not mention this |
| **L5** tools | the OCR tool and the vision model disagree about the code |
| **L6** validation | how do you contract-test "actually looked at the image"? |
| **L7** trace | your audit log now contains screenshots of people's desktops |

Plus one genuinely new class: **cross-modal contradiction.** The employee's text
says one thing, the screenshot says another, and neither source is malfunctioning.
Something has to decide, and *"the model will notice"* is not an architecture.

### Six perceptual failure modes

| Mode | Example here | Control |
|---|---|---|
| **Resolution loss** | is that `VPN-403` or `VPN-408`? | ask for `legibility` as a **separate field** |
| **Ambiguity** | two error codes on screen, which is the cause? | allow `"ambiguous"` as an answer |
| **Cross-modal contradiction** | text says timeout, screenshot says certificate | extract **per-source first**, reconcile second |
| **Spatial reasoning** | which dialog is in front? | anchor to labels, not positions |
| **OCR confusion** | `0`/`O`, `1`/`l`, `403`/`408` | never let vision be the sole source of an identifier |
| **Confident hallucination** | a username that is not on screen | require a grounding phrase per claim |
'''),

        code('''
# ============================================================
# A SYNTHETIC SCREENSHOT — with a defect planted on purpose
# ============================================================
from PIL import Image, ImageDraw, ImageFilter, ImageFont

def _font(size: int, bold: bool = False):
    for p in [f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
              f"/usr/share/fonts/truetype/liberation/LiberationSans{'-Bold' if bold else '-Regular'}.ttf",
              f"/System/Library/Fonts/Supplemental/Arial{' Bold' if bold else ''}.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: continue
    return ImageFont.load_default()

def render_vpn_error(blur_error_code: bool = True) -> Image.Image:
    """We RENDER the screenshot rather than shipping a PNG, for one reason that
    matters: it lets us plant the defect at a known location. A real screenshot
    contains an illegible digit only if you are lucky; here it is guaranteed,
    identical for everyone, and reproducible on every run."""
    W, H = 900, 560
    img = Image.new("RGB", (W, H), (238, 240, 244))
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 46], fill=(48, 62, 92))                       # title bar
    d.text((18, 12), "Corporate VPN Client", font=_font(19, True), fill=(255, 255, 255))
    d.text((W - 34, 12), "✕", font=_font(19), fill=(230, 230, 230))

    d.rectangle([40, 92, W - 40, H - 96], fill=(255, 255, 255), outline=(198, 202, 210), width=1)
    d.ellipse([70, 124, 114, 168], fill=(198, 58, 52))
    d.text((86, 133), "!", font=_font(26, True), fill=(255, 255, 255))

    d.text((136, 126), "Connection failed", font=_font(23, True), fill=(28, 30, 36))
    d.text((136, 162), "Unable to establish a secure tunnel.", font=_font(15), fill=(90, 94, 104))

    code_xy = (136, 210)
    d.text(code_xy, "Error: VPN-403", font=_font(20, True), fill=(28, 30, 36))
    d.text((136, 248), "Certificate validation failed", font=_font(15), fill=(70, 74, 84))
    d.text((136, 286), "Server:  vpn.corp.example", font=_font(15), fill=(70, 74, 84))
    d.text((136, 314), "Adapter: Corp VPN Virtual NIC #2", font=_font(15), fill=(70, 74, 84))
    d.text((136, 342), "Last successful connection: 11/09/2026 09:14",
           font=_font(15), fill=(70, 74, 84))

    for label, x, fill, tc in [("Retry", W - 300, (52, 96, 190), (255, 255, 255)),
                               ("Cancel", W - 170, (232, 234, 238), (40, 42, 48))]:
        d.rectangle([x, H - 78, x + 118, H - 40], fill=fill,
                    outline=(150, 154, 162), width=1)
        d.text((x + 34, H - 68), label, font=_font(15), fill=tc)

    if blur_error_code:
        # THE PLANTED DEFECT: blur only the error NUMBER. Everything else stays
        # crisp -- which makes this a resolution problem, not a bad-screenshot
        # problem, and makes the model's silence about it instructive.
        box = (code_xy[0] + 74, code_xy[1] - 4, code_xy[0] + 148, code_xy[1] + 28)
        img.paste(img.crop(box).filter(ImageFilter.GaussianBlur(radius=2.4)), box)
    return img

screenshot = render_vpn_error()
screenshot_path = "vpn_error_screenshot.png"
screenshot.save(screenshot_path)
display(screenshot)
print("The error code is deliberately blurred. Can YOU read it with certainty?")
'''),

        predict('''
The model is about to see that screenshot.

The error code is genuinely ambiguous — `VPN-403` and `VPN-408` are both
plausible readings. **Will the model say it cannot read it, or will it pick one
and report it with the same confidence it reports the server name?**
'''),

        code('''
# ============================================================
# THE STRUCTURED MULTIMODAL ENVELOPE — the part that is ARCHITECTURE
# ============================================================
def to_data_url(img: Image.Image) -> str:
    buf = __import__("io").BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

VISION_SCHEMA = {
    "type": "object",
    "properties": {
        "error_code":        {"type": ["string", "null"]},
        "error_code_legible":{"type": "string", "enum": ["CLEAR", "PARTIAL", "ILLEGIBLE"]},
        "stated_cause":      {"type": ["string", "null"]},
        "server":            {"type": ["string", "null"]},
        "all_text_read":     {"type": "array", "items": {"type": "string"}},
        "illegible_regions": {"type": "array", "items": {"type": "string"}},
        "grounding":         {"type": "string"},
        "cannot_determine":  {"type": "array", "items": {"type": "string"}},
    },
    "required": ["error_code", "error_code_legible", "stated_cause", "server",
                 "all_text_read", "illegible_regions", "grounding", "cannot_determine"],
    "additionalProperties": False,
}

VISION_SYSTEM = (
    "You are the PERCEPTION component of an IT service desk copilot. Your job is "
    "to report what a screenshot actually shows -- not to diagnose it.\\n\\n"
    "Rules:\\n"
    "- If you cannot read something with certainty, mark it ILLEGIBLE. A guess "
    "recorded as a fact is the most damaging thing you can do here.\\n"
    "- Report text exactly as printed, before interpreting it.\\n"
    "- For every claim, say WHERE on the screen you saw it.\\n"
    "- Do not recommend a fix. That is a different component's job."
)

vision_msgs = [
    {"role": "system", "content": VISION_SYSTEM},
    {"role": "user", "content": [
        {"type": "text", "text":
            "EVIDENCE 1: screenshot\\n"
            "source: employee's own device, submitted at intake\\n"
            "trust: employee-supplied\\n"
            "extract specifically: the error code, the stated cause, the server, "
            "and anything you cannot read.\\n"},
        {"type": "image_url",
         "image_url": {"url": to_data_url(screenshot), "detail": "high"}},
        {"type": "text", "text": "Return the JSON object only."},
    ]},
]

vis = llm_chat(vision_msgs, schema=VISION_SCHEMA, max_tokens=900)
perception = json.loads(vis.text)
print(json.dumps(perception, indent=2))
print(f"\\n[{vis.prompt_tokens} prompt tokens, ${vis.cost_usd:.6f}, {vis.latency_ms:.0f} ms]")
'''),

        code('''
# ============================================================
# DID IT ADMIT WHAT IT COULD NOT READ?
# ============================================================
# We RENDERED this image, so unlike any real screenshot we have GROUND TRUTH.
# That is the whole reason to generate evidence rather than ship a stock photo:
# you can score perception instead of admiring it.
TRUE_ERROR_CODE = "VPN-403"

reported  = perception.get("error_code")
legible   = perception.get("error_code_legible")
admitted  = bool(perception.get("illegible_regions") or perception.get("cannot_determine")) \
            or legible in ("PARTIAL", "ILLEGIBLE")
correct   = (reported or "").strip().upper() == TRUE_ERROR_CODE

print(f"ground truth (we drew it) : {TRUE_ERROR_CODE}")
print(f"model reported            : {reported}")
print(f"legibility claim          : {legible}")
print(f"admitted any uncertainty  : {admitted}")
print()

if correct and admitted:
    print("BEST CASE: read it correctly AND flagged that it was hard to read.")
elif correct and not admitted:
    print("LUCKY: correct, but claimed certainty it had not earned. Run it again --")
    print("this is the outcome that varies most between runs, and a control whose")
    print("success depends on the run is not a control.")
elif not correct and admitted:
    print("ACCEPTABLE: it got the value WRONG but SAID SO. Downstream can now treat")
    print("the code as missing evidence and ask for a clearer screenshot. A wrong")
    print("answer that knows it might be wrong is a recoverable failure.")
else:
    print("!! THE FAILURE THIS SECTION EXISTS FOR:")
    print(f"   It reported {reported} as CLEAR. The true value is {TRUE_ERROR_CODE}.")
    print("   Wrong, and confident, and indistinguishable from its correct answers --")
    print("   note that it read the server, the adapter and the timestamp perfectly.")
    print()
    print("   This is CONFIDENT HALLUCINATION plus OCR CONFUSION in one field, and")
    print("   no amount of prompting removes it. The architectural response is not")
    print("   'ask the model to try harder'; it is:")
    print("     - never let a vision model be the SOLE source of an identifier")
    print("     - cross-check the code against a known list of valid error codes")
    print("     - route an unverifiable code to a human, not to a runbook lookup")

print()
print("Either way, note WHY the model could have flagged it: `error_code_legible`")
print("and `illegible_regions` exist as fields. Remove them, ask 'what is the")
print("error code?', and you get a code. Always a code.")
'''),

        code('''
# ============================================================
# THE DOWNSTREAM COST OF ONE MISREAD CHARACTER
# ============================================================
VALID_ERROR_CODES = {"VPN-401": "Authentication failed",
                     "VPN-403": "Certificate validation failed",
                     "VPN-408": "Connection timed out",
                     "VPN-500": "Gateway unavailable"}

code_seen = (perception.get("error_code") or "").strip().upper()
print(f"model reported : {code_seen}")
if code_seen in VALID_ERROR_CODES:
    print(f"in catalogue   : yes -> {VALID_ERROR_CODES[code_seen]}")
    print("The runbook lookup proceeds. If the code was misread but happens to be")
    print("a VALID code, you now route to a confidently wrong runbook.")
else:
    print(f"in catalogue   : NO")
    print(f"valid codes    : {sorted(VALID_ERROR_CODES)}")
    print()
    print("A four-line set membership test just caught a perception error that the")
    print("model reported as CLEAR. This is the cheapest control in this section:")
    print("**validate extracted identifiers against a closed list you already own.**")
    print("You do not need to know the right answer -- only that this is not one.")


# ============================================================
# CROSS-MODAL CONTRADICTION — the genuinely new failure class
# ============================================================
# The employee's text and their screenshot disagree. Neither is malfunctioning.
EMPLOYEE_TEXT = ("The VPN keeps timing out — it just hangs and eventually says the "
                 "connection timed out. Started after the laptop update.")
# ...but the screenshot says "Certificate validation failed", which is not a timeout.

reconcile_msgs = [
    {"role": "system", "content":
        "You reconcile evidence from multiple sources for an IT service desk.\\n"
        "Extract from EACH source independently BEFORE comparing them. Never "
        "invent a story that accommodates both -- report the contradiction. "
        "Contradictions are the most valuable thing you can find."},
    {"role": "user", "content": [
        {"type": "text", "text":
            f"EVIDENCE 1: employee's written description\\n"
            f"trust: employee-supplied (an account, not a measurement)\\n"
            f"---\\n{EMPLOYEE_TEXT}\\n---\\n"},
        {"type": "text", "text":
            "EVIDENCE 2: screenshot from the same employee's device\\n"
            "trust: employee-supplied, but a direct capture of system output\\n"},
        {"type": "image_url",
         "image_url": {"url": to_data_url(screenshot), "detail": "high"}},
        {"type": "text", "text":
            "\\nDo these two sources agree on the CAUSE of the failure? "
            "Answer in under 120 words. If they disagree, say exactly how, and "
            "say which source you would trust for the cause and why."},
    ]},
]

recon = llm_chat(reconcile_msgs, max_tokens=400)
print(recon.text)
'''),

        md('''
### Why that matters more than it looks

A timeout and a certificate failure have **completely different runbooks**. If
the copilot takes the employee's word, it retrieves the wrong section, gives
advice that cannot work, and the ticket bounces.

The employee is not lying. They are describing *what they experienced* — hanging,
then a failure — while the screenshot reports *what the system measured*. Both
are true; only one is diagnostic.

> **Per-source extraction first, reconciliation second.** Never ask one question
> that spans two sources — a model asked to summarise contradictory evidence will
> usually synthesise a coherent story that accommodates both, because coherence
> is what it was trained to produce.
'''),

        breaks('''
**Your audit log now contains screenshots of employees' desktops** — open
windows, email subject lines, customer names, whatever was on screen.

Where you would see it: not in an error, ever. You see it in a data-protection
review, and by then you have months of retained personal data.

Controls: strip images from traces by default, store a hash and a short
description instead of the bytes, set a shorter retention for image payloads
than for text, and put a size cap and format allow-list at L1.
'''),

        # ================================================================
        md("---\n\n# 19. Protocol-driven tool integration (real MCP)"),

        why('''
Today the copilot calls `get_ticket`. Tomorrow the ticketing team ships a new
endpoint; next quarter the same three tools are needed by the adjuster
assistant, the onboarding bot and a Slack app.

Count the integrations:

```text
   3 applications  ×  4 tools  =  12 bespoke integrations
```

Each with its own auth, error handling, schema drift and on-call. Add a fifth
tool and you write three more; add a fourth app and you write four more.

**This is the N×M problem**, and it is where a great deal of engineering time
quietly dies.
'''),

        analogy('''
Your kettle does not know whether the electricity came from a coal plant, a
solar farm, or a diesel generator in the basement. It knows 230V, 50Hz and a
plug shape.

That ignorance is not a limitation — **it is the entire value.** The grid can be
rebuilt underneath the kettle and the kettle does not care, and a kettle
manufacturer never has to talk to a power company.

```text
   without a protocol :  N apps × M tools      =  N × M
   with a protocol    :  N clients + M servers =  N + M
```
'''),

        what('''
**MCP (Model Context Protocol)** is a socket for tools. We are going to run a
**real** one — an actual server process, spoken to over stdio — because a
simulated protocol teaches the vocabulary while hiding the only thing that makes
protocols matter: **the process boundary.**

What appears once the boundary is real:

| | What it gives you |
|---|---|
| **Discovery** | the client asks what tools exist; it was never told |
| **Versioning** | the server adds a tool; no client redeploys |
| **Isolation** | a tool crashes; the app survives |
| **Authority** | the server decides what it exposes, not the caller |
| **Latency** | a process hop is not free — and now you can measure it |

> **Colab note.** The MCP SDK is async and Colab already runs an event loop, so
> the obvious `asyncio.run(...)` raises *"This event loop is already running"* —
> the single most common reason people give up on MCP in a notebook. The client
> below runs its own loop on a background thread instead of monkey-patching
> yours.
'''),

        code('''
# ============================================================
# WRITE A REAL MCP SERVER TO DISK
# ============================================================
# It runs as a SEPARATE PROCESS. Note that it re-creates the same SQLite
# queries -- because it is a different program, which is exactly the point.
MCP_SERVER_SRC = r\'\'\'
import json, sqlite3, sys
from typing import Any, Dict

DB = sys.argv[1] if len(sys.argv) > 1 else "enterprise_support.db"

def _row(query: str, params: tuple):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        r = conn.execute(query, params).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()

def get_ticket(ticket_id: str) -> str:
    row = _row("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id.upper(),))
    if row is None:
        return json.dumps({"ok": True, "data": {"found": False, "ticket_id": ticket_id.upper()}})
    return json.dumps({"ok": True, "data": {"found": True, **row}})

def check_entitlement(employee_id: str) -> str:
    row = _row("SELECT * FROM entitlements WHERE employee_id = ?", (employee_id,))
    if row is None:
        return json.dumps({"ok": True, "data": {"found": False, "employee_id": employee_id}})
    return json.dumps({"ok": True, "data": {"found": True, **row}})

SCHEMAS = {
    "get_ticket": {
        "type": "object",
        "properties": {"ticket_id": {"type": "string", "pattern": "^INC-[0-9]{4}$"}},
        "required": ["ticket_id"], "additionalProperties": False},
    "check_entitlement": {
        "type": "object",
        "properties": {"employee_id": {"type": "string", "pattern": "^E[0-9]{4}$"}},
        "required": ["employee_id"], "additionalProperties": False},
}
DESCRIPTIONS = {
    "get_ticket": ("Read the current state of a support ticket from the ticketing "
                   "system. Use this before any statement about ticket status."),
    "check_entitlement": ("Read an employee's software and administrator access "
                          "entitlements. Use this before answering any access question."),
}

def build():
    from mcp.server import MCPServer
    from mcp.server.mcpserver.tools.base import Tool as MCPTool
    tools = []
    for fn in (get_ticket, check_entitlement):
        t = MCPTool.from_function(fn, name=fn.__name__,
                                  description=DESCRIPTIONS[fn.__name__],
                                  structured_output=False)
        # Hand the SDK OUR schema. A signature-derived one loses the pattern
        # constraints, and the schema is the contract.
        t.parameters = SCHEMAS[fn.__name__]
        tools.append(t)
    return MCPServer(name="servicedesk-tools", version="1.0.0", tools=tools)

if __name__ == "__main__":
    import asyncio
    # stdout is the PROTOCOL CHANNEL. A stray print() here corrupts the JSON-RPC
    # stream and produces a baffling client-side parse error. Diagnostics go to
    # stderr, always.
    asyncio.run(build().run_stdio_async())
\'\'\'

with open("mcp_servicedesk_server.py", "w") as f:
    f.write(MCP_SERVER_SRC)
print("wrote mcp_servicedesk_server.py — a standalone MCP server")
'''),

        code('''
# ============================================================
# THE CLIENT — its own event loop, so Colab needs no patching
# ============================================================
import asyncio, threading
from contextlib import AsyncExitStack

class _LoopThread:
    """An asyncio loop on a dedicated thread. Work is submitted and awaited
    synchronously, so the notebook keeps its ordinary top-to-bottom feel while
    a genuinely async client runs underneath."""
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._run, daemon=True).start()
    def _run(self):
        asyncio.set_event_loop(self._loop); self._loop.run_forever()
    def call(self, coro, timeout=60):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)
    def stop(self):
        self._loop.call_soon_threadsafe(self._loop.stop)


class MCPToolClient:
    """Exposes the SAME surface as our in-process tools: .names, .schemas(), .run()."""
    def __init__(self, script: str, db: str = "enterprise_support.db"):
        self.script, self.db = script, db
        self._loop = self._session = self._stack = None
        self.discovered: List[Dict[str, Any]] = []

    def connect(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._loop = _LoopThread()
        params = StdioServerParameters(command=sys.executable,
                                       args=[self.script, self.db], env=dict(os.environ))

        async def _open():
            stack = AsyncExitStack()
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()             # the handshake
            listing = await session.list_tools()   # DISCOVERY
            self._session, self._stack = session, stack
            # v1 called this `inputSchema`; v2 calls it `input_schema`.
            return [{"name": t.name, "description": t.description or "",
                     "input_schema": getattr(t, "input_schema", None)
                                     or getattr(t, "inputSchema", None) or {}}
                    for t in listing.tools]

        self.discovered = self._loop.call(_open())
        return self

    @property
    def names(self) -> List[str]:
        return sorted(t["name"] for t in self.discovered)

    def schemas(self) -> List[Dict[str, Any]]:
        return [{"type": "function",
                 "function": {"name": t["name"], "description": t["description"],
                              "parameters": t["input_schema"]}}
                for t in self.discovered]

    def run(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        if self._session is None:
            return ToolResult(False, error="not connected", tool=name)
        async def _call():
            return await self._session.call_tool(name, arguments or {})
        try:
            resp = self._loop.call(_call())
        except Exception as exc:
            return ToolResult(False, error=f"MCP transport error: {exc}", tool=name)

        texts = [c.text for c in resp.content if getattr(c, "type", None) == "text"]
        raw = texts[0] if texts else ""
        if bool(getattr(resp, "is_error", None) or getattr(resp, "isError", None)):
            return ToolResult(False, error=raw or "tool call failed", tool=name)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return ToolResult(True, data=raw, tool=name)
        if isinstance(payload, dict) and "ok" in payload:
            return ToolResult(bool(payload["ok"]), data=payload.get("data"),
                              error=payload.get("error"), tool=name)
        return ToolResult(True, data=payload, tool=name)

print("MCP client defined")
'''),

        predict('''
The client is about to connect. **It has not been told what tools exist** — the
word `get_ticket` does not appear anywhere in `MCPToolClient`.

How will it find out? And what would happen tomorrow if the server exposed a
third tool?
'''),

        code('''
# ============================================================
# CONNECT — a real subprocess, a real handshake, real discovery
# ============================================================
mcp_client = MCPToolClient("mcp_servicedesk_server.py").connect()

print("this notebook's pid :", os.getpid())
print("DISCOVERED over the protocol (not hard-coded):")
for t in mcp_client.discovered:
    print(f"   {t['name']}")
    print(f"      {t['description'][:88]}...")
    print(f"      schema: {json.dumps(t['input_schema'])[:96]}")
'''),

        code('''
# ============================================================
# CALL ACROSS THE PROCESS BOUNDARY — and compare to in-process
# ============================================================
t0 = time.perf_counter(); local  = run_tool("get_ticket", {"ticket_id": "INC-1042"})
t1 = time.perf_counter(); remote = mcp_client.run("get_ticket", {"ticket_id": "INC-1042"})
t2 = time.perf_counter()

print(f"in-process : ok={local.ok}   status={local.data['status']:<14} "
      f"{(t1 - t0) * 1000:6.2f} ms")
print(f"over MCP   : ok={remote.ok}   status={remote.data['status']:<14} "
      f"{(t2 - t1) * 1000:6.2f} ms")
print()
print("Same data. Different process. The latency difference IS the protocol tax --")
print("and now it is a number you can put in a design discussion.")
print()
print("errors still come back as DATA, not exceptions, across the boundary:")
for name, args in [("drop_database", {}), ("get_ticket", {})]:
    r = mcp_client.run(name, args)
    print(f"  {name:<16} ok={r.ok}  {str(r.error)[:60]}")
'''),

        code('''
# ============================================================
# THE SWAP — the orchestrator cannot tell them apart
# ============================================================
def answer_with_registry(question: str, tool_source, employee_id: str = "E1001") -> str:
    """`tool_source` is either our in-process TOOLS dict or the MCP client.
    Note that this function contains no branch on which one it is."""
    if isinstance(tool_source, MCPToolClient):
        schemas, runner = tool_source.schemas(), tool_source.run
    else:
        schemas = [t["schema"] for t in tool_source.values()]
        runner = run_tool

    messages = service_desk_hierarchy().compile(
        trusted_context={"employee_id": employee_id},
        untrusted={"Employee message": question},
        user_task=f"Employee {employee_id} asks: {question}",
    )
    out = llm_chat(messages, tools=schemas)
    if out.wants_tools:
        messages.append({"role": "assistant", "content": out.text or None,
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name,
                                                      "arguments": tc.function.arguments}}
                                        for tc in out.tool_calls]})
        for tc in out.tool_calls:
            res = runner(tc.function.name, json.loads(tc.function.arguments or "{}"))
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": res.to_model_string()})
        out = llm_chat(messages, tools=schemas)
    return out.text

Q = "What is the status of INC-1042?"
print("IN-PROCESS TOOLS")
print(" ", answer_with_registry(Q, TOOLS)[:260])
print()
print("OVER A REAL MCP SERVER  (one argument changed)")
print(" ", answer_with_registry(Q, mcp_client)[:260])
'''),

        md('''
### What changed, and what did not

**Did not change:** the prompt hierarchy, the orchestration, the guardrails, the
trace format, the answer.

**Did change:** where the tools live, and the latency.

That is the definition of a protocol working — you replaced the entire transport
and the system above it did not notice.

### The honest accounting

Say this part out loud, because MCP is currently being recommended in places
where it is the wrong call:

| You gain | You pay |
|---|---|
| Discovery, versioning, isolation, authority, reuse | Serialisation, a process to supervise, a new failure surface, harder debugging, latency |

**Use a protocol when:** another team owns the tool · the tool outlives the app ·
several applications need it · it needs its own release cadence or security
boundary.

**Don't when:** it is three functions in one codebase with one consumer.

> For this copilot *today*, the in-process registry is the right call. The moment
> the onboarding bot also needs `get_ticket`, MCP starts paying for itself.
> **Knowing which situation you are in is the actual architectural skill.**

And one limit worth stating plainly: **a protocol solves plumbing, never
meaning.** If the ticketing team changes `status` from a string to an enum with
different values, every consumer breaks regardless of MCP. That needs
*versioning*, not a protocol.
'''),

        code('''
mcp_client._loop and mcp_client._loop.stop()
print("MCP server stopped.")
'''),

        # ================================================================
        md("---\n\n# 20. End to end"),

        md('''
Everything assembled, on one realistic request:

> *"INC-1042 is blocking production access. What's the current status and should
> this be escalated?"*

Watch each layer do its one job.
'''),

        code('''
# ============================================================
# THE COMPLETE COPILOT
# ============================================================
def copilot(question: str, employee_id: str = "E1001",
            agent_role: str = "employee") -> Dict[str, Any]:
    h = service_desk_hierarchy()
    trace = Trace(question, employee_id, h.fingerprint)

    # L1 — intake
    s = trace.span("intake", "L1")
    employee = get_employee(employee_id)
    if not employee.get("found"):
        s.finish(ok=False)
        return {"answer": "Unknown employee.", "trace": trace, "approvals": []}
    s.finish(ok=True, employee=employee["name"], chars=len(question))

    # L2 — classify, then plan and act within a budget
    s = trace.span("classify", "L2")
    decision, err, raw = classify(question)
    s.finish(intent=decision.intent if decision else "PARSE_FAIL",
             injection_flag=decision.injection_attempt if decision else None,
             tokens=raw.total_tokens, cost=raw.cost_usd)

    s = trace.span("agent_loop", "L2/L4/L5")
    run = run_agent(question, employee_id=employee_id)
    s.finish(steps=len(run.steps), tools=",".join(run.tool_calls) or "—",
             stopped=run.stopped_because, tokens=run.total_tokens, cost=run.total_cost)

    # L6 — every queued write goes through authorization
    s = trace.span("guardrails", "L6")
    approvals = []
    for w in run.pending_writes:
        verdict = authorize(ToolAction(tool=w["tool"], arguments=w["arguments"]),
                            employee_id=employee_id, agent_role=agent_role)
        approvals.append({"tool": w["tool"], "arguments": w["arguments"],
                          "verdict": str(verdict),
                          "needs_confirmation": verdict.requires_confirmation})
    s.finish(writes_proposed=len(run.pending_writes),
             writes_executed=0,
             rules_fired=";".join(a["verdict"].split(":")[0] for a in approvals) or "—")

    # L6 — output-side checks: grounding, and unverified action claims
    s = trace.span("grounding_check", "L6")
    cited = set(CITATION_RE.findall(run.answer or ""))
    s.finish(citations=",".join(sorted(cited)) or "—",
             tool_evidence=len(run.tool_calls))

    s = trace.span("action_claim_check", "L6")
    claim_violations = check_action_claims(run.answer or "", run.tool_calls)
    s.finish(unverified_claims=len(claim_violations),
             rule=claim_violations[0].rule if claim_violations else "—")

    return {"answer": run.answer or "", "trace": trace, "approvals": approvals,
            "run": run, "claim_violations": claim_violations}



# An explicit INSTRUCTION, not a question -- so the write path actually fires.
# ("should this be escalated?" is a question, and the model correctly answers
# it rather than acting. Worth noticing: that is good behaviour, and it is why
# the approval demo needs an imperative.)
result = copilot("Please escalate INC-1042 — it is blocking production work.")

print(result["answer"])
print()
if result["claim_violations"]:
    print("!! OUTPUT GUARDRAIL FIRED:")
    for v in result["claim_violations"]:
        print("  ", v)
    print("   The answer claims an action that never executed. In production this")
    print("   reply would be blocked and regenerated, not sent.")
else:
    print("Output check: no unverified action claims. Good.")
'''),

        code('''
print("=" * 78)
print("TRACE")
print("=" * 78)
display(result["trace"].dataframe())

print("PENDING APPROVALS (nothing was executed):")
for a in result["approvals"] or [{"verdict": "  none proposed"}]:
    print("  ", a.get("tool", ""), a["verdict"])

print()
print("AUDIT RECORD:")
print(json.dumps(result["trace"].audit_record(), indent=2))
'''),

        code('''
# ============================================================
# NOW THE EXPLICIT ACTION — with a human in the loop
# ============================================================
# The employee asked. An AGENT approves. Only then does state change.
pending = result["approvals"]
if pending:
    action = ToolAction(tool=pending[0]["tool"], arguments=pending[0]["arguments"])

    as_employee = authorize(action, "E1001", agent_role="employee")
    as_agent    = authorize(action, "E1001", agent_role="service_desk_agent")
    print("as employee          :", as_employee)
    print("as service desk agent:", as_agent)
    print()

    if as_agent.requires_confirmation:
        print("--- a human clicks Approve ---")
        executed = run_tool(action.tool, action.arguments)
        print("executed:", json.dumps(executed.data, indent=2, default=str))
        print()
        print("THIS is the difference between answer generation and controlled")
        print("enterprise action. The model proposed it three steps ago; a person")
        print("authorised it; the system executed it; the trace records all three.")
else:
    print("The model did not propose a write for this request.")
    print("Re-run with an explicit 'please escalate INC-1042' to see the path.")
'''),

        # ================================================================
        md('''
---

# 21. Failure-mode analysis

A mature architect asks *"how can this fail?"* — not *"how do I make the demo
work?"*

| Failure | Example here | Layer | Control | Where you'd see it |
|---|---|---|---|---|
| Hallucination | invented an SLA | L4 | RAG + citation enforcement | grounding check: uncited sentences |
| Retrieval miss | "hanging" ≠ "freezing" | L5 | embeddings, hybrid, benchmark | hit-rate drop in retrieval eval |
| Fabricated citation | cites `KB-002` for an SLA | L4 | check cited ⊆ retrieved | `hallucinated_citations` non-empty |
| Prompt injection | fake manager approval | **L3** | structural quarantine | `injection_attempt` + canary in evals |
| Tool misuse | closes a P1 | **L6** | authorization + confirmation | `writes_intercepted` in the trace |
| Cross-employee leak | reads someone else's data | L6 | tenancy check | `DP-01` rule firing |
| Infinite loop | same tool 11× | **L2** | budgets + repeat detection | repeated `act` rows |
| Silent cost blowout | context tripled | L7 | cost per fingerprint | cost jump on a fingerprint change |
| Stale knowledge | last year's policy, cited | L5 | freshness metadata, review cycle | **nothing — this is the scary one** |
| Perceptual error | misread `403` as `408` | L4 | legibility as a separate field | `error_code_legible` |
| Data leakage | screenshots in logs | L7 | redaction, retention | a DP review, months later |

Two patterns worth naming:

1. **The symptom appears in a different layer from the defect.** Wrong arithmetic
   looks like a model problem; it is a missing tool. A successful injection looks
   like a model problem; it is prompt assembly. This is why "the AI is
   unreliable" is not a diagnosis.
2. **The last two rows have no automated detector.** Some failures are only
   caught by process — a document review cycle, a data-protection review. Knowing
   which of your risks are *not* covered by monitoring is itself a deliverable.
'''),

        md('''
---

# 22. Production hardening checklist

### Architecture
- [ ] One adapter between the application and the model provider
- [ ] Every tool has an explicit, strict schema
- [ ] Read-only and side-effecting tools are classified, and the classification is enforced
- [ ] Deterministic work (arithmetic, state transitions, authorization) is outside the model

### Security
- [ ] Authentication, and identity flowed through to tool authorization
- [ ] Untrusted content quarantined — **including retrieved documents and tool results**
- [ ] Tool scoping per workflow (least privilege)
- [ ] No secrets in prompts; no PII in traces beyond your retention policy
- [ ] An injection canary in the eval suite

### Reliability
- [ ] Timeouts on every model and tool call
- [ ] Retries with a limit, and a circuit breaker
- [ ] Step / tool / token budgets, **and a test that fires each one**
- [ ] Repeat-call detection
- [ ] Defined fallback when the provider is down

### Quality
- [ ] A golden eval set, with every production incident added to it
- [ ] Retrieval evaluated separately from generation
- [ ] Grounding / citation checks
- [ ] Tool-selection tests
- [ ] Evals run in CI, not manually

### Operations
- [ ] Trace per request, with a **prompt fingerprint**
- [ ] Token and cost per request, aggregated by fingerprint
- [ ] Latency broken down by step
- [ ] A feedback channel from users into the eval set

### Governance
- [ ] An approved model list and a change process
- [ ] Prompt changes versioned and reviewed like code
- [ ] Audit trail for every state change, with who approved it
- [ ] A human escalation path that people actually use
'''),

        md('''
---

# 23. Capstone

## Enterprise Support Agent 2.0

Extend this notebook to handle:

> *"My laptop is freezing during Teams calls. Also, I can't install the
> monitoring tool I need. Here's a screenshot."*

### Required

1. Classify as a **multi-part** request (endpoint + software + image)
2. Retrieve **both** the endpoint runbook and the software policy
3. Check the employee's actual entitlement — never infer it from their role
4. Extract from the screenshot with a **legibility field**
5. Reconcile the screenshot against the written description; report contradictions
6. Produce a diagnosis that separates **evidence** from **recommendation**
7. Never grant admin privileges; propose an approval request instead
8. Emit a **structured action proposal**, not prose, for anything with a side effect
9. Require confirmation before any state change
10. Produce a trace with tokens, cost and every guardrail that fired

### Stretch

- Conversation memory across turns (and a token budget for it)
- Hybrid retrieval — fuse TF-IDF and embedding rankings, then re-measure
- A reranker over the top 20 retrieved documents
- An LLM-as-judge groundedness scorer, validated against your own labels
- Model routing: a cheaper model for status lookups, a stronger one for diagnosis
- Prompt versioning with fingerprints recorded per response
- An injection canary that runs on every deploy
- Move all five tools behind the MCP server, not just two

### How to know you have finished

Not "it answers well". You are finished when you can state, for each of the
seven layers, **one realistic failure and where you would see it in the trace** —
and when a guardrail you wrote has actually fired in a test you wrote.
'''),

        md('''
---

# 24. Interview questions

**Foundations**
1. Why is an LLM not a GenAI system? Give a failure that a better model does not fix.
2. When would you use RAG, and when a tool? What decides it?
3. What is a prompt hierarchy, and what problem does provenance solve?
4. Why is temperature 0 not a determinism guarantee?

**Design**
5. Where should authorization live, and why not in the prompt?
6. How would you evaluate a RAG system, dimension by dimension?
7. A model proposes closing a P1 ticket. Walk through everything between the
   proposal and the state change.
8. How do you stop an agent loop? Name three independent controls.
9. Your retrieval quality drops after a chunking change. How do you know before
   a user tells you?

**Advanced**
10. Design tenant isolation for a multi-customer copilot.
11. How do you version prompts and run regression tests against them?
12. When is MCP worth its cost, and when is it overhead?
13. A tool's semantics change (fraud bands become a 1–5 scale). What breaks, and
    what would have prevented it?
14. How would you route between a small and a large model, and how would you know
    the routing was right?
15. Your audit log contains screenshots. What is your retention design?
16. Name a failure in your system that **no monitoring will catch**. What process
    covers it instead?
'''),

        md('''
---

# 25. The final mental model

```text
                         USER
                           │
                           ▼
                      APPLICATION            L1  interface, authn, limits
                           │
                           ▼
                      ORCHESTRATOR           L2  budgets, termination, routing
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          PROMPT        MEMORY          RAG    L3  tiers + quarantine
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                          LLM                 L4  judgement. Nothing else.
                           │
                 ┌─────────┼─────────┐
                 ▼         ▼         ▼
               TOOLS     APIs     SEARCH      L5  reach, deterministic
                 │         │         │
                 └─────────┼─────────┘
                           ▼
                      VALIDATION              L6  schema, authz, business rules
                           │
                           ▼
                      GUARDRAILS              L6  block / downgrade / confirm
                           │
                           ▼
                       RESPONSE  —or—  APPROVED ACTION

Cross-cutting:  SECURITY │ GOVERNANCE │ EVALUATION │ OBSERVABILITY │ COST   L7
```

### The seven sentences

1. **The model is the pilot. Everything else is the airline.**
2. **The model proposes. Only your system decides.**
3. **The prompt makes the right behaviour likely; the guardrail makes the wrong behaviour impossible.**
4. **Untrusted content is evidence, never instructions** — including retrieved documents and tool results.
5. **If a correct answer exists, compute it. If judgement is required, generate it — then constrain it.**
6. **A screenshot is a second witness, not a judge.**
7. **A hallucination is usually a missing tool** — and without a trace, none of the above is debuggable.

### The central principle

> **Use the model for probabilistic language and reasoning tasks. Use
> deterministic software to enforce business rules, authorization, transactions
> and system state.**

That separation is the foundation of everything in this notebook. Every section
was one more place to draw the line.

---

## Where to go next

- **`notebooks/01`–`06`** in this repository teach the same architecture against
  an insurance claims-triage system, with a reusable Python package, a test
  suite and an instructor guide. Deeper on prompt hierarchies, guardrail design
  and MCP.
- **The appendix below** sketches how each lab component maps to its production
  equivalent.
'''),

        md('''
---

# Appendix — production evolution

This lab starts simple on purpose. The **architecture stays conceptually stable
while individual components are replaced**:

| Layer | This lab | Production |
|---|---|---|
| System of record | SQLite | ServiceNow / Jira APIs |
| Retrieval | TF-IDF → OpenAI embeddings | Hybrid search + reranker in a vector DB |
| Model access | OpenAI direct | An enterprise gateway with quotas and logging |
| Tools | Python functions | Versioned services, some behind MCP |
| Authorization | a function | An IAM / policy engine (OPA, Cedar) |
| Traces | a dataclass | OpenTelemetry → your observability platform |
| Evaluation | cells in a notebook | An eval platform running in CI |
| Secrets | env var | A secrets manager |
| Approval | `input()`-style gate | A real workflow with an audit trail |

If you can draw the seven layers, name what each one owns, and say how each one
fails — **you can now do this in any stack.** That was the point.
'''),
    ]
