"""Notebook 05 — Protocols & interoperability (25 min)."""
from __future__ import annotations

from nbtools import code, md, predict, standard_opening

FILE = "05_protocols_and_mcp.ipynb"


def build():
    c = standard_opening(
        FILE,
        title="Notebook 05 — Tool Integration and Protocol-Driven Interoperability",
        subtitle=(
            "We will move Meridian's three tools into a **separate process** behind a "
            "real MCP server, change one line of the system, and watch nothing else "
            "need to change. That is what a protocol buys you."
        ),
        duration="25 min",
        mode="Conceptual + Guided Analysis",
        where="**L5** — how the system reaches things it does not own.",
        takeaway=(
            "**A protocol turns N×M bespoke integrations into N+M.** The cost is a "
            "process boundary and everything that comes with one — so use it when tools "
            "outlive the app that calls them, and not before."
        ),
    )

    c += [
        md('''
---

## WHY — the integration that eats your roadmap

Meridian's triage system calls three tools. Then the fraud team ships a new
endpoint. Then the policy system is migrated. Then someone wants the same three
tools available in the adjuster's chat assistant, and in the underwriting bot,
and in the internal Slack app.

Now count the integrations:

```
   3 applications  ×  4 tools   =  12 bespoke integrations
```

Each with its own auth, its own error handling, its own schema drift, and its
own on-call. Add a fifth tool and you write three more. Add a fourth app and
you write four more. **This is the N×M problem**, and it is where a great deal
of engineering time quietly dies.

### The analogy — the electrical socket

Your kettle does not know whether the electricity came from a coal plant, a
solar farm, or a diesel generator in the basement. It knows **230V, 50Hz, and a
plug shape.**

That ignorance is not a limitation. It is the entire value:

- The grid can be rebuilt underneath the kettle and the kettle does not care.
- A kettle manufacturer never has to talk to a power company.
- A new appliance works on day one, with no negotiation.

A protocol is a socket. **MCP is that socket for tools:**

```
   without a protocol :  N apps × M tools  =  N × M integrations
   with a protocol    :  N clients + M servers  =  N + M
```

Same argument as USB, ODBC, LSP and OpenAPI before it. And *"MCP is just
JSON-RPC"* misses the point in exactly the way *"HTTP is just text over TCP"*
does.
'''),

        md('''
## WHAT — where we are now: tools in-process

Right now Meridian's three tools are Python functions in the same process as
the orchestrator. Let's look at what that gives us — and what it doesn't.
'''),

        code('''
# ============================================================
# THE IN-PROCESS REGISTRY — what we have been using all session
# ============================================================
from meridian import default_registry
import json

registry = default_registry()
print("tools:", registry.names)
print()

schema = registry.schemas()[0]
print(json.dumps(schema, indent=2)[:900])
'''),

        md('''
### The three rules of the tool layer

Before we move anything, these are what make a tool layer *work* — and they
hold whether the tool is in-process or across a network:

**1. A tool must never raise.**
An exception becomes a stack trace in the orchestrator, and the run dies
holding information the model could have recovered from. Return a structured
error; let the model read it and decide.

**2. The description is the API.**
The model chooses tools by reading descriptions, and it reads them the way a
new hire reads a wiki — literally, without context. A description saying *what*
a tool does but not *when to use it* produces a model that calls it at the
wrong moment.

**3. The schema is the contract.**
Loose schemas don't fail loudly. They fail as a `policy_id` of
`"the one in the claim"`.

Let's check rule 1 actually holds.
'''),

        code('''
# Rule 1: tools must never raise. Four ways to abuse the registry:
print("unknown tool     ->", registry.run("delete_all_claims", {}).error)
print("missing argument ->", registry.run("lookup_policy", {}).error[:80])
print("wrong type       ->", registry.run("compute_payout",
      {"policy_id": "POL-88120", "assessed_amount_inr": "about fifty thousand"}).error[:80])
print("not found        ->", registry.run("lookup_policy",
      {"policy_id": "POL-00000"}).data)
print()
print("Four abuses, zero exceptions. Note the last one: 'not found' came back")
print("as a RESULT, not an error -- an error suggests the system is broken and")
print("the model should retry; a null result is information to reason about.")
'''),

        md('''
---

## HOW — the same three tools, behind a real protocol

Now we cross a **real process boundary**. `meridian/mcp_server.py` is an actual
MCP stdio server; `mcp_client.py` spawns it and speaks the protocol to it.

This is deliberately not simulated. A simulated protocol teaches the
vocabulary — "server", "discovery", "JSON-RPC" — while hiding the only thing
that makes protocols matter.

> **Colab note.** The MCP SDK is async, and Colab already runs an event loop,
> so the obvious `asyncio.run(...)` raises *"This event loop is already
> running"*. That is the single most common reason people give up on MCP in a
> notebook. `mcp_client.py` runs its own loop on a background thread instead of
> monkey-patching yours — one more example of an ugly runtime detail isolated
> inside one adapter so nothing above it has to know.
'''),

        predict("The client is about to connect. It has **not** been told what tools exist. How will it find out — and what would happen if the server exposed a fourth tool tomorrow?"),

        code('''
# ============================================================
# CONNECT TO A REAL MCP SERVER (spawned as a subprocess)
# ============================================================
import os, sys
from meridian.mcp_client import MCPToolRegistry, mcp_available

print("MCP SDK available:", mcp_available())

# The server must be importable as `python -m meridian.mcp_server`, so the
# subprocess needs the repo on its PYTHONPATH.
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(
    __import__("meridian").__file__)))
child_env = dict(os.environ)
child_env["PYTHONPATH"] = repo_root + os.pathsep + child_env.get("PYTHONPATH", "")

mcp = MCPToolRegistry(env=child_env)
mcp.connect()

print("connected. pid of this notebook:", os.getpid())
print()
print("DISCOVERY — tools learned over the protocol, not hard-coded:")
for t in mcp.discovered:
    print(f"   {t['name']}")
    print(f"      {t['description'][:110]}...")
'''),

        md('''
### That listing is the whole point

The client source code does **not** contain the words `lookup_policy`,
`fraud_signal` or `compute_payout`. It asked, and the server answered.

Which means: **the server can add a fourth tool tomorrow and this client picks
it up on its next connect, with no redeploy.** That is not achievable with a
hand-rolled registry, because a hand-rolled registry is a list you have to
edit.
'''),

        code('''
# Call a tool across the process boundary. Same ToolResult type as in-process.
result = mcp.run("lookup_policy", {"policy_id": "POL-88120"})
print("ok  :", result.ok)
print("data:", json.dumps(result.data, indent=2)[:420])
'''),

        code('''
# Error handling ACROSS the boundary — rule 1 still holds over a socket.
print("unknown tool ->", mcp.run("drop_database", {}).error)
print("bad args     ->", mcp.run("lookup_policy", {}).error[:90])
print()
print("The server did not crash. The client did not raise. The error came back")
print("as data the model can act on -- which is rule 1, now enforced across a")
print("process boundary rather than inside one.")
'''),

        md('''
---

## The swap — one line, and nothing else changes

Here is the demonstration the whole notebook exists for.

`MCPToolRegistry` exposes **the same interface** as `ToolRegistry`:
`.names`, `.schemas()`, `.run(name, arguments)`.

So the orchestrator cannot tell them apart.
'''),

        predict("We are about to run the identical claim twice — once with in-process tools, once over MCP. What will differ in the decision? What will differ in the trace?"),

        code('''
# ============================================================
# THE SWAP — in-process vs. across a process boundary
# ============================================================
from meridian import TriageOrchestrator

in_process = TriageOrchestrator(registry=default_registry())
over_mcp   = TriageOrchestrator(registry=mcp)          # <-- the ONLY change

r_local = in_process.run("CLM-4417")
r_mcp   = over_mcp.run("CLM-4417")

print("IN-PROCESS ->", r_local.decision.recommendation,
      f"| {r_local.trace.total_ms} ms | tools: {r_local.trace.tool_calls}")
print("OVER MCP   ->", r_mcp.decision.recommendation,
      f"| {r_mcp.trace.total_ms} ms | tools: {r_mcp.trace.tool_calls}")
'''),

        code('''
from meridian import compare
print(compare(r_local.trace, r_mcp.trace))
'''),

        md('''
### What changed, and what did not

**Did not change:** the orchestrator, the prompt hierarchy, the guardrails, the
output contract, the trace format, the decision.

**Did change:** latency (a process hop is not free), and where the tools live.

That is the definition of a protocol working. You replaced the entire
transport, and the system above it did not notice.

> The tools did not change either. `mcp_server.py` imports **the same `Tool`
> objects** the in-process registry uses. Only the transport moved.
'''),

        md('''
---

## The honest accounting — what a protocol costs

Say this part out loud in the room, because "adopt MCP" is currently being
recommended in a lot of places where it is the wrong call.

| You gain | You pay |
|---|---|
| **Discovery** — clients learn tools at runtime | **Serialisation** on every call |
| **Versioning** — server evolves without client redeploys | **A process to supervise**, restart, monitor |
| **Isolation** — a tool crash doesn't take the app down | **A new failure surface** (transport, handshake, timeouts) |
| **Authority** — the server decides what it exposes | **Harder local debugging** — your stack trace ends at the boundary |
| **Reuse** — one server, many clients | **Latency** — measurable, as you just saw |

### When to reach for it

**Use a protocol when:**
- the tool is owned by **another team** (this is the big one),
- the tool **outlives** the app calling it,
- **several** applications need the same tool,
- the tool needs its own release cadence, or its own security boundary.

**Don't, when:**
- it's three functions in one codebase with one consumer.

> For Meridian *today*, the in-process registry is the right call. The moment
> the underwriting bot and the adjuster assistant both need `lookup_policy`,
> MCP starts paying for itself.
>
> **Knowing which situation you are in is the actual architectural skill.**
> Adopting a protocol because it is fashionable is how you acquire a
> distributed system you did not need.
'''),

        md('''
---

## The failure mode that will cost you an afternoon

`stdout` is the **protocol channel** for an MCP stdio server. A single stray
`print()` in server code corrupts the JSON-RPC stream, and the client reports a
baffling parse error that points nowhere near the actual bug.

```python
# in your MCP server:
print("debug: looking up policy")        # ← corrupts the protocol stream
print("debug: ...", file=sys.stderr)     # ← correct
```

Worth knowing before you spend an afternoon on it. Diagnostics go to stderr,
always.
'''),

        code('''
# ============================================================
# TOOL SCOPING — the cheapest security control in the stack
# ============================================================
# A tool that is not in the registry cannot be called, no matter what the model
# decides or what a claimant writes in their statement.
from meridian.tools import ToolRegistry, LOOKUP_POLICY

read_only = ToolRegistry([LOOKUP_POLICY])      # deliberately one tool
print("scoped registry:", read_only.names)

scoped = TriageOrchestrator(registry=read_only)
r = scoped.run("CLM-4417")

print()
print("tools the model actually managed to call:", r.trace.tool_calls)
print("decision:", r.decision.recommendation, "| confidence:", r.decision.confidence)
print("missing evidence:", r.decision.missing_evidence)
print()
print("It could not reach the fraud platform or the payout calculator, so it")
print("should be reporting lower confidence and naming what it lacks. Scoping")
print("a workflow to the minimum tools it needs costs nothing and bounds the")
print("blast radius of every other failure in the system.")
'''),

        code('''
# Always shut the subprocess down.
mcp.close()
print("MCP server stopped.")
'''),

        md('''
---

## Exercise — draw the integration (7 min)

Meridian wants the adjuster's **chat assistant** and the **underwriting bot**
to use `lookup_policy` too. The policy administration team will own the tool.

In pairs, sketch:

1. How many integrations **without** a protocol? How many **with**?
2. Who owns the server? Who owns the schema? What happens when the policy team
   adds a field?
3. The fraud model is retrained and its band values change from
   `LOW/MEDIUM/HIGH` to a 1–5 scale. Which of the three consumers break, and
   what would have prevented that?
4. The chat assistant should read policies but **never** compute payouts. Where
   is that enforced — client, server, or both?

<details>
<summary>Discussion notes</summary>

1. Without: 3 apps × 4 tools = **12**. With: 3 clients + 4 servers = **7**, and
   the gap widens with every addition.
2. The policy team owns server *and* schema — that is the point, the team that
   owns the data owns its interface. Adding a field is backward-compatible if
   consumers ignore unknown fields, which is a client design rule worth writing
   down.
3. **All three break**, and a protocol does not save you: this is a *semantic*
   change, not a transport change. What prevents it is **versioning** —
   `fraud_signal_v2` alongside v1 — and a deprecation window. Worth stressing:
   a protocol solves plumbing, never meaning.
4. **Both.** The server enforces it (authority belongs with the owner of the
   tool), and the client scopes its registry (defence in depth, and it stops
   the model from even seeing a tool it should not use). Same argument as
   prompt-vs-guardrail in notebook 03.
</details>
'''),

        md('''
---

## Where we are — the stack is complete

Five blocks, seven layers, one system:

| Notebook | Layer(s) | What you now know |
|---|---|---|
| 01 | all | The stack, and that boundaries are only real if crossing them breaks something |
| 02 | L2, L4 | Why runtime-decided step counts force orchestration |
| 03 | L3 | Prompting as access control; structure beats wording |
| 04 | L1, L3, L4 | Multimodality multiplies failure modes at every layer |
| 05 | L5 | Protocols turn N×M into N+M — at a real cost |

**The takeaway for the whole session:**
> **The model is the doctor. Your system is the hospital.**

Notebook 06 puts all seven layers together on one claim, then asks you to
**diagram and explain a complete GenAI system architecture** — which is the
outcome this session exists to produce.

### Before you move on
- [ ] Can you explain N×M → N+M to someone who has never heard of MCP?
- [ ] Can you name three things you pay for a protocol?
- [ ] Can you state the rule for when a protocol is worth it?
- [ ] Why does a protocol not save you when a tool's *semantics* change?
'''),
    ]
    return c
