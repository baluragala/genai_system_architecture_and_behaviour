"""Pre-flight check for the instructor. Run this the day before you teach.

    python scripts/smoke.py

`pytest` proves the SYSTEM works, using a stubbed model. This proves your KEY
works, your model is reachable, the vision path is alive and the MCP subprocess
starts — the four things that actually fail on the morning of a session.

Costs roughly half a cent.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS, FAIL = "  ok  ", " FAIL "
failures: list[str] = []


def check(label: str, fn) -> None:
    started = time.perf_counter()
    try:
        detail = fn()
        ms = int((time.perf_counter() - started) * 1000)
        print(f"[{PASS}] {label:<44} {ms:>6} ms   {detail or ''}")
    except Exception as exc:  # noqa: BLE001 - this is a report, not a library
        ms = int((time.perf_counter() - started) * 1000)
        print(f"[{FAIL}] {label:<44} {ms:>6} ms   {type(exc).__name__}: {exc}")
        failures.append(label)


def main() -> int:
    print("=" * 92)
    print("MERIDIAN PRE-FLIGHT".center(92))
    print("=" * 92)

    # ---- the package -----------------------------------------------------
    def imports():
        import meridian
        return f"meridian {meridian.__version__}"

    check("package imports", imports)

    def deps():
        import openai, PIL  # noqa: F401
        out = [f"openai {openai.__version__}", f"pillow {PIL.__version__}"]
        try:
            import mcp  # noqa: F401
            import importlib.metadata as md
            out.append(f"mcp {md.version('mcp')}")
        except Exception:
            out.append("mcp MISSING (notebook 05 will not run)")
        return ", ".join(out)

    check("dependencies importable", deps)

    # ---- the key ---------------------------------------------------------
    def key():
        from meridian.config import load_api_key
        k = load_api_key()
        return f"...{k[-4:]}"

    check("OPENAI_API_KEY resolves", key)

    if failures:
        print("\nStopping: fix the above before running the live checks.")
        return 1

    # ---- L4, for real ----------------------------------------------------
    def model():
        from meridian import get_llm
        out = get_llm().complete(
            [{"role": "user", "content": "Reply with exactly: READY"}], max_tokens=10)
        return f"{out.text.strip()[:20]!r}  ${out.cost_usd:.6f}"

    check("model call (L4)", model)

    # ---- the whole stack -------------------------------------------------
    def full():
        from meridian import TriageOrchestrator
        r = TriageOrchestrator().run("CLM-4417")
        assert r.ok, r.error
        return (f"{r.decision.recommendation}  tools={r.trace.tool_calls}  "
                f"${r.trace.total_cost_usd:.5f}")

    check("full stack, happy path (CLM-4417)", full)

    def guarded():
        from meridian import TriageOrchestrator
        r = TriageOrchestrator().run("CLM-4420")
        assert r.ok, r.error
        assert r.decision.recommendation == "DECLINE", (
            f"expected DECLINE on a lapsed policy, got {r.decision.recommendation}")
        return f"DECLINE, {len(r.decision.violations)} guardrail(s) fired"

    check("guardrail holds on lapsed policy (CLM-4420)", guarded)

    # ---- notebook 04 -----------------------------------------------------
    def vision():
        from meridian import get_llm
        from meridian.multimodal import render_repair_invoice, to_data_url
        out = get_llm().complete([{"role": "user", "content": [
            {"type": "text", "text": "Reply with only the invoice number."},
            {"type": "image_url",
             "image_url": {"url": to_data_url(render_repair_invoice()), "detail": "high"}},
        ]}], max_tokens=40)
        return f"{out.text.strip()[:34]!r}  ({out.prompt_tokens} prompt tokens)"

    check("vision path (L4 multimodal)", vision)

    # ---- notebook 05 -----------------------------------------------------
    def mcp_roundtrip():
        from meridian.mcp_client import MCPToolRegistry, mcp_available
        if not mcp_available():
            raise RuntimeError("mcp not installed — pip install 'mcp>=2,<3'")
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ)
        env["PYTHONPATH"] = repo + os.pathsep + env.get("PYTHONPATH", "")
        with MCPToolRegistry(env=env) as m:
            names = m.names
            r = m.run("lookup_policy", {"policy_id": "POL-88120"})
            assert r.ok and r.data["status"] == "ACTIVE"
        return f"discovered {names}"

    check("MCP server round trip (L5)", mcp_roundtrip)

    print("=" * 92)
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED: {', '.join(failures)}")
        print("See teaching/instructor_guide.md -> 'What will go wrong'.")
        return 1
    print("All checks passed. You are ready to teach.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
