"""
mcp_client.py — the socket side. Spawns the server, discovers tools, calls them.
================================================================================

WHY this file exists
--------------------
`mcp_server.py` is the appliance. This is the plug. Between them sits a real
process boundary, which is the only reason notebook 05 teaches anything that a
mock could not.

The class below exposes **the same interface as `ToolRegistry`** —
`.schemas()`, `.run(name, arguments)`, `.names`. That is not a convenience; it
is the demonstration:

    orch = TriageOrchestrator(registry=default_registry())   # in-process
    orch = TriageOrchestrator(registry=MCPToolRegistry())    # separate process

One line changes. The orchestrator, the prompts, the guardrails and the trace
are untouched. **That is what a protocol buys you**, and saying it is much less
convincing than running it.

THE COLAB PROBLEM (and why the code below looks like this)
----------------------------------------------------------
The MCP Python SDK is async. Jupyter and Colab already run an asyncio event
loop in the main thread, so the obvious `asyncio.run(...)` raises
`RuntimeError: This event loop is already running` — which is the single most
common reason people give up on MCP in a notebook.

There are two fixes. `nest_asyncio` patches the running loop, which works but
is invasive and interacts badly with some libraries. Instead this client runs
its own event loop on a **dedicated background thread** and hands work to it.
That is more code, but it is honest, it does not monkey-patch anyone else's
runtime, and it behaves identically in a notebook, a script and a test.

The session's own architectural lesson applies to this file too: the messy
runtime detail is isolated in one adapter so nothing above it has to know.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from concurrent.futures import Future
from typing import Any, Callable, Dict, List, Optional

from .tools import ToolResult


class _LoopThread:
    """An asyncio event loop living on its own thread.

    Everything async in this module is submitted here and awaited
    synchronously by the caller, so the notebook keeps its ordinary
    top-to-bottom feel while a real async client runs underneath.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="meridian-mcp-loop")
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def call(self, coro, timeout: float = 60.0) -> Any:
        return self.submit(coro).result(timeout=timeout)

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)


class MCPToolRegistry:
    """A ToolRegistry backed by a real MCP server in a separate process.

    Usage (the notebook does exactly this):

        mcp = MCPToolRegistry()
        mcp.connect()                 # spawns the server, performs discovery
        print(mcp.names)              # <- learned over the protocol, not hard-coded
        result = mcp.run("lookup_policy", {"policy_id": "POL-88120"})
        ...
        mcp.close()

    Or as a context manager:

        with MCPToolRegistry() as mcp:
            ...
    """

    def __init__(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.command = command or sys.executable
        self.args = args if args is not None else ["-m", "meridian.mcp_server"]
        self.env = env
        self._loop: Optional[_LoopThread] = None
        self._session: Any = None
        self._exit_stack: Any = None
        self._discovered: List[Dict[str, Any]] = []
        self.connected = False

    # -- lifecycle ----------------------------------------------------------

    def connect(self, timeout: float = 60.0) -> "MCPToolRegistry":
        """Spawn the server and perform the MCP handshake + tool discovery."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("pip install 'mcp>=2,<3'") from exc

        from contextlib import AsyncExitStack

        self._loop = _LoopThread()
        params = StdioServerParameters(command=self.command, args=self.args, env=self.env)

        async def _open() -> List[Dict[str, Any]]:
            # The exit stack is kept alive across calls: the server is a
            # long-lived subprocess, not a request-scoped one. Spawning a
            # process per tool call would work and would also be an excellent
            # way to make a 40 ms call take 900 ms.
            stack = AsyncExitStack()
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()          # <- the handshake
            listing = await session.list_tools()  # <- DISCOVERY
            self._session = session
            self._exit_stack = stack
            # The SDK renamed this field between v1 (`inputSchema`) and v2
            # (`input_schema`). Tolerating both is three lines here and saves a
            # baffling AttributeError in a room full of people whose Colab just
            # installed a different version from yours.
            return [
                {"name": t.name,
                 "description": t.description or "",
                 "input_schema": getattr(t, "input_schema", None)
                                 or getattr(t, "inputSchema", None)
                                 or {"type": "object", "properties": {}}}
                for t in listing.tools
            ]

        self._discovered = self._loop.call(_open(), timeout=timeout)
        self.connected = True
        return self

    def close(self) -> None:
        if self._loop and self._exit_stack is not None:
            async def _close() -> None:
                await self._exit_stack.aclose()
            try:
                self._loop.call(_close(), timeout=10)
            except Exception:  # pragma: no cover - teardown is best-effort
                pass
        if self._loop:
            self._loop.stop()
        self.connected = False
        self._session = None
        self._exit_stack = None

    def __enter__(self) -> "MCPToolRegistry":
        return self.connect()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- the ToolRegistry interface ----------------------------------------
    # Identical surface to tools.ToolRegistry. That is the point of the whole
    # notebook: the orchestrator cannot tell these two apart.

    @property
    def names(self) -> List[str]:
        return sorted(t["name"] for t in self._discovered)

    def __contains__(self, name: str) -> bool:
        return name in self.names

    def __len__(self) -> int:
        return len(self._discovered)

    @property
    def discovered(self) -> List[Dict[str, Any]]:
        """The raw discovery payload — worth printing in the room."""
        return self._discovered

    def schemas(self) -> List[Dict[str, Any]]:
        """Translate MCP tool descriptors into OpenAI tool-calling shape.

        Note that this adapter is ~6 lines. Two protocols, both describing
        'a function with a JSON Schema', and the bridge between them is
        trivial *because they are both protocols*. Bridging two bespoke
        integrations is where the work actually is.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in self._discovered
        ]

    def run(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Invoke a tool over the protocol. Returns the same ToolResult type."""
        if not self.connected or self._session is None:
            return ToolResult(ok=False, error="MCP client is not connected", tool=name)
        if "__malformed__" in (arguments or {}):
            return ToolResult(ok=False, tool=name,
                              error="arguments were not valid JSON; re-issue with valid JSON")

        async def _call() -> Any:
            return await self._session.call_tool(name, arguments or {})

        try:
            response = self._loop.call(_call(), timeout=60)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — transport failures are data too
            return ToolResult(ok=False, error=f"MCP transport error: {exc}", tool=name)

        texts = [c.text for c in response.content
                 if getattr(c, "type", None) == "text"]
        raw = texts[0] if texts else ""

        # The SDK signals a failed call with an is_error flag and PLAIN TEXT
        # content — not with our JSON envelope, because the failure happened in
        # the SDK's dispatch layer before our code ran (unknown tool name,
        # arguments that did not validate). Normalising it back into the same
        # ToolResult shape is what keeps the orchestrator unable to tell the two
        # transports apart, which is the whole claim of notebook 05.
        #
        # v1 spelled this `isError`; v2 spells it `is_error`.
        is_error = bool(getattr(response, "is_error", None)
                        or getattr(response, "isError", None))
        if is_error:
            return ToolResult(ok=False, error=raw or "tool call failed", tool=name)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return ToolResult(ok=True, data=raw, tool=name)

        # Our own envelope from mcp_server.py: {"ok": ..., "data"/"error": ...}
        if isinstance(payload, dict) and "ok" in payload:
            return ToolResult(ok=bool(payload["ok"]), data=payload.get("data"),
                              error=payload.get("error"), tool=name)
        return ToolResult(ok=True, data=payload, tool=name)


def mcp_available() -> bool:
    """Is the MCP SDK importable? Used by the notebook to give a clear message."""
    try:
        import mcp  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False
