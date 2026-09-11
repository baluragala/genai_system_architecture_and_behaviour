"""
mcp_server.py — a REAL Model Context Protocol server. Run as a subprocess.
==========================================================================

WHY this file exists
--------------------
The agenda's last block is *protocols and interoperability*, and there is
exactly one way to teach a protocol honestly: **cross a real process
boundary.** A simulated protocol teaches the vocabulary — "server", "tool
discovery", "JSON-RPC" — while hiding the only thing that makes protocols
matter.

THE ANALOGY — the electrical socket
-----------------------------------
Your kettle does not know whether the electricity came from a coal plant, a
solar farm or a diesel generator in the basement. It knows 230V, 50Hz, and a
plug shape. That ignorance is not a limitation — it is the entire value. It
means the grid can be rebuilt underneath the kettle and the kettle does not
care, and it means a kettle manufacturer never has to talk to a power company.

MCP is that socket for tools:

    without a protocol   every app writes a bespoke integration per tool.
                         N apps x M tools = N x M integrations.
    with a protocol      every tool exposes one server; every app speaks one
                         client. N + M.

That is the whole argument. It is the same argument as USB, ODBC, LSP and
OpenAPI before it, and it is why "MCP is just JSON-RPC" misses the point in
the same way "HTTP is just text over TCP" does.

WHAT CHANGES WHEN THE BOUNDARY IS REAL
--------------------------------------
Notebook 05 moves Meridian's three tools behind this server, and the things
that appear are precisely the things a simulation cannot show you:

    discovery     the client asks what tools exist; it was not told
    versioning    the server can add a tool without the client redeploying
    isolation     the tool crashes; the client survives
    authority     the server decides what it exposes, not the caller
    latency       a process hop is not free, and now you can see it

WHAT IT COSTS
-------------
Say this in the room, because the honest answer is not "nothing":
serialisation, a process to supervise, a new failure surface, and harder local
debugging. A protocol is worth it when tools outlive the app that calls them,
or when somebody else owns the tool. For three functions in one codebase, a
plain registry is the right call — and knowing which situation you are in is
the actual architectural skill.

RUNNING IT
----------
    python -m meridian.mcp_server          # stdio, speaks MCP
    # or let mcp_client.py spawn it for you, which is what the notebook does
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Dict, List

from .tools import COMPUTE_PAYOUT, FRAUD_SIGNAL, LOOKUP_POLICY, Tool

__server_version__ = "1.0.0"

# The same three Tool objects the in-process registry uses. That is deliberate:
# notebook 05's punchline is that the TOOLS did not change, only the transport.
EXPOSED: List[Tool] = [LOOKUP_POLICY, FRAUD_SIGNAL, COMPUTE_PAYOUT]


# JSON Schema -> Python annotation. Small on purpose: if a tool ever needs a
# type that is not here, that is a signal the tool is doing too much.
_PY_TYPES = {"string": str, "number": float, "integer": int, "boolean": bool,
             "array": list, "object": dict}


def _wrap(tool: Tool):
    """Turn a meridian Tool into a function the MCP SDK can register.

    WHY THIS IS NOT JUST `def fn(**kwargs)`
    ---------------------------------------
    The SDK validates incoming arguments against the wrapper's **actual Python
    signature**, not against the schema we advertise. A `**kwargs` wrapper
    therefore advertises `policy_id` and then rejects it, which produces the
    memorably unhelpful error `rejected arguments: ['kwargs']`.

    So we synthesise a real signature from the tool's own JSON Schema. This is
    the sort of glue every protocol adapter accumulates, and it is worth seeing
    rather than hiding: **a protocol removes N x M integrations; it does not
    remove the need to understand the two things you are joining.**

    Note that the SDK's derived validation is laxer than the schema we publish
    (it checks types, not the `^POL-[0-9]{5}$` pattern). That matches the
    in-process registry, which does not check patterns either — so both
    transports behave identically, which is what notebook 05 needs to be true.
    The pattern's job is to tell the *model* what a valid argument looks like.
    """
    props: Dict[str, Any] = tool.parameters.get("properties", {})
    required = set(tool.parameters.get("required", []))

    params, annotations = [], {}
    for name, spec in props.items():
        annotations[name] = _PY_TYPES.get(spec.get("type"), Any)
        params.append(name if name in required else f"{name}=None")

    src = f"def {tool.name}({', '.join(params)}):\n    return _call(locals())\n"

    def _call(kwargs: Dict[str, Any]) -> str:
        # Drop unsupplied optionals so the underlying function's own defaults
        # apply, rather than being overwritten with None.
        cleaned = {k: v for k, v in kwargs.items()
                   if v is not None or k in required}
        return tool.run(**cleaned).to_model_string()   # never raises

    namespace: Dict[str, Any] = {"_call": _call}
    exec(src, namespace)                                # noqa: S102 - built from our own schema
    fn = namespace[tool.name]
    fn.__annotations__ = {**annotations, "return": str}
    fn.__doc__ = tool.description
    return fn


def _build_server():
    """Construct the MCP server. Imported lazily so the package imports without `mcp`.

    Note the `parameters` override below. The SDK will happily derive a schema
    from a function signature, but the derived schema loses the constraints we
    actually care about — the `^POL-[0-9]{5}$` pattern, `additionalProperties:
    false`, the minimums. Those are the contract (rule 3 in `tools.py`), so we
    hand the SDK the schema we wrote rather than one inferred from type hints.
    """
    try:
        from mcp.server import MCPServer
        from mcp.server.mcpserver.tools.base import Tool as MCPTool
    except (ModuleNotFoundError, ImportError) as exc:  # pragma: no cover
        raise RuntimeError(
            "This server targets the MCP Python SDK v2.x. In the notebook the "
            "bootstrap cell handles it; otherwise:  pip install 'mcp>=2,<3'"
        ) from exc

    registered = []
    for tool in EXPOSED:
        mcp_tool = MCPTool.from_function(
            _wrap(tool),
            name=tool.name,
            description=tool.description,   # rule 2: the description IS the API
            structured_output=False,
        )
        mcp_tool.parameters = tool.parameters   # rule 3: our schema, not an inferred one
        registered.append(mcp_tool)

    return MCPServer(name="meridian-claims", version=__server_version__,
                     tools=registered)


async def _amain() -> None:
    await _build_server().run_stdio_async()


def main() -> None:
    """Entry point. stdout is the PROTOCOL CHANNEL — never print to it.

    A stray `print()` in an MCP stdio server corrupts the JSON-RPC stream and
    produces a baffling client-side parse error. This is a real and very common
    bug, so it is worth pointing at during the session: diagnostics go to
    stderr, always.
    """
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:  # pragma: no cover
        print("meridian-claims MCP server stopped", file=sys.stderr)


if __name__ == "__main__":
    main()
