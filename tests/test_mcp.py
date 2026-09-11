"""MCP integration tests — a real subprocess, a real protocol handshake.

These are the tests that would have caught every bug found while building
notebook 05: an SDK API change, a field renamed between major versions, a
wrapper whose signature did not match its advertised schema, and error
responses that came back as plain text instead of our JSON envelope.

They spawn an actual server, so they are slower than the rest of the suite.
That is the correct trade: the whole point of notebook 05 is that the boundary
is real, and a mocked test of a protocol tests nothing.
"""
from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("mcp", reason="MCP SDK not installed")

from conftest import ScriptedLLM, decision_json          # noqa: E402

from meridian.mcp_client import MCPToolRegistry           # noqa: E402
from meridian.orchestrator import TriageOrchestrator      # noqa: E402
from meridian.tools import default_registry               # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def mcp():
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
    registry = MCPToolRegistry(env=env)
    registry.connect()
    yield registry
    registry.close()


def test_discovery_finds_the_tools_without_being_told(mcp):
    """The client source never names these tools. It asked; the server answered."""
    assert mcp.names == ["compute_payout", "fraud_signal", "lookup_policy"]


def test_discovered_schemas_match_the_in_process_ones(mcp):
    """The punchline of notebook 05: the TOOLS did not change, only the transport."""
    local = {s["function"]["name"]: s["function"] for s in default_registry().schemas()}
    remote = {s["function"]["name"]: s["function"] for s in mcp.schemas()}

    assert set(local) == set(remote)
    for name in local:
        assert local[name]["parameters"] == remote[name]["parameters"], name
        assert local[name]["description"] == remote[name]["description"], name


def test_strict_schema_survives_the_protocol_hop(mcp):
    """If the SDK silently derived a schema from the signature, the pattern and
    additionalProperties would be gone — and 'the schema is the contract' would
    quietly stop being true over the wire."""
    params = next(s["function"]["parameters"] for s in mcp.schemas()
                  if s["function"]["name"] == "lookup_policy")
    assert params["properties"]["policy_id"]["pattern"] == "^POL-[0-9]{5}$"
    assert params["additionalProperties"] is False


def test_calls_return_the_same_data_as_in_process(mcp):
    local = default_registry()
    for name, args in [
        ("lookup_policy", {"policy_id": "POL-88120"}),
        ("lookup_policy", {"policy_id": "POL-88123"}),
        ("fraud_signal", {"claim_id": "CLM-4420"}),
        ("compute_payout", {"policy_id": "POL-88120", "assessed_amount_inr": 38500}),
    ]:
        assert mcp.run(name, args).data == local.run(name, args).data, (name, args)


def test_optional_arguments_keep_their_defaults_across_the_boundary():
    """`apply_depreciation` is optional. If the wrapper passed None instead of
    omitting it, the underlying default would be destroyed and payouts would be
    wrong only over MCP — the nastiest possible bug shape."""
    local = default_registry().run(
        "compute_payout", {"policy_id": "POL-88121", "assessed_amount_inr": 100_000})
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
    with MCPToolRegistry(env=env) as remote:
        out = remote.run("compute_payout",
                         {"policy_id": "POL-88121", "assessed_amount_inr": 100_000})
    assert out.data["depreciation_inr"] == local.data["depreciation_inr"] == 10_000


@pytest.mark.parametrize("name,args", [
    ("drop_database", {}),                       # hallucinated tool
    ("lookup_policy", {}),                       # missing required argument
    ("lookup_policy", {"__malformed__": "{"}),   # model emitted bad JSON
])
def test_errors_come_back_as_data_not_exceptions(mcp, name, args):
    """Rule 1 of the tool layer, enforced across a process boundary."""
    result = mcp.run(name, args)
    assert result.ok is False
    assert result.error


def test_a_failed_call_does_not_kill_the_server(mcp):
    """Isolation: the thing a protocol gives you that an in-process call cannot."""
    assert mcp.run("drop_database", {}).ok is False
    assert mcp.run("lookup_policy", {"policy_id": "POL-88120"}).ok is True


def test_orchestrator_cannot_tell_the_two_registries_apart(mcp):
    """The one-line swap from notebook 05, asserted."""
    script = lambda: [
        {"tools": [("lookup_policy", {"policy_id": "POL-88120"}),
                   ("fraud_signal", {"claim_id": "CLM-4417"})]},
        {"text": decision_json()},
    ]
    local = TriageOrchestrator(llm=ScriptedLLM(script()),
                               registry=default_registry()).run("CLM-4417")
    remote = TriageOrchestrator(llm=ScriptedLLM(script()),
                                registry=mcp).run("CLM-4417")

    assert local.decision.recommendation == remote.decision.recommendation
    assert local.trace.tool_calls == remote.trace.tool_calls
    assert local.decision.to_dict() == remote.decision.to_dict()


def test_disconnected_client_reports_rather_than_raises():
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO
    never_connected = MCPToolRegistry(env=env)
    out = never_connected.run("lookup_policy", {"policy_id": "POL-88120"})
    assert out.ok is False
    assert "not connected" in out.error
