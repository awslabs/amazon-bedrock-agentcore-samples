"""Unit checks for forced tool calls on the write path.

**What is worth testing here is not that forcing works — it is the two ways forcing goes wrong.**
Setting `tool_choice` is one line; the failure modes are that a name Bedrock does not recognise
aborts
the request, and that forcing *every* model call in a turn loops forever (the event loop re-invokes
the
model with the tool result, and a still-forced choice obliges another call). Both are asserted
below,
against the real `InvokeModelContext` rather than a stand-in — the whole point is that the dataclass
the
SDK passes is the one the handler reshapes.

The agent and its tool registry are faked, deliberately: this exercises the handler's decision, and
a
mocked `Agent` would only assert that the mock behaves like the mock. That forcing actually stops
the
stall is a *live* claim, measured by repeated runs of `scripts/verify_conversation_api.py`, and no
offline test can stand in for it.

**The module under test lives in the agent package, not beside this file** — `agentcore.json` sets
one
`codeLocation` (`app/MultiTenantTravel/`), so anything outside it is not deployed and anything
inside it
ships.
Tests belong out of the deployment zip, so they stay in the repository-level `agent/tests`
directory.

Run: `python -m pytest agent/tests/test_tool_choice.py -q` (or execute the file directly).
Needs `strands-agents >= 1.50.2` on the path; below that the middleware seam does not exist and the
checks skip rather than fail, because that is the environment and not the code.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parents[1] / "MultiTenantTravel" / "app" / "MultiTenantTravel"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

import tool_choice  # noqa: E402

try:
    from strands._middleware import InvokeModelContext, InvokeModelStage

    HAVE_MIDDLEWARE = True
except ImportError:  # pragma: no cover - environment, not code
    HAVE_MIDDLEWARE = False

# The gateway-prefixed names, which are what the model is shown and therefore what `toolChoice` must
# use. Spelled out rather than imported from the BFF: this asserts the two agree, and importing the
# thing under test from the thing it must match would assert nothing.
PREPARE = "booking___prepare_booking"
SEARCH = "search___search_flights"


class FakeTool:
    """Only `tool_name` matters — it is the single attribute `tool_choice.force` reads."""

    def __init__(self, name: str) -> None:
        self.tool_name = name


class FakeRegistry:
    def __init__(self) -> None:
        self.added: list[tuple[object, object]] = []

    def add_middleware(self, phase: object, handler: object) -> None:
        self.added.append((phase, handler))


class FakeAgent:
    def __init__(self) -> None:
        self._middleware_registry = FakeRegistry()


TOOLS = [FakeTool(PREPARE), FakeTool(SEARCH)]

# A fresh ask, and the event loop coming back with a tool result. The second is the shape that must
# *not* be forced.
USER_TURN = [
    {"role": "user", "content": [{"text": "Prepare a booking for hotel option opt_x now."}]}
]
TOOL_LOOP = [
    {"role": "user", "content": [{"toolResult": {"toolUseId": "t1", "status": "success"}}]}
]


def _installed(tool_name: str = PREPARE):
    """Install forcing on a fake agent and return `(agent, handler)`."""
    agent = FakeAgent()
    assert tool_choice.force(agent, tool_name, TOOLS) is True
    phase, handler = agent._middleware_registry.added[0]
    assert phase is InvokeModelStage.Input, (
        "forcing must run in the input phase, before the model call"
    )
    return agent, handler


def _context(agent: object, messages: list[dict], choice: dict | None = None):
    return InvokeModelContext(
        agent=agent,
        messages=messages,
        system_prompt="system",
        tool_specs=[],
        tool_choice=choice,
        invocation_state={},
        model=object(),
    )


def test_a_read_tool_cannot_be_forced_even_though_the_turn_offers_it():
    """**The check that `force_tool` is not a client-chosen instruction.**

    `SEARCH` is in `TOOLS`, so the old test — "is this name among the turn's tools?" — passed
    it. That made every tool forceable by anything able to reach the runtime with a valid token,
    including the three write tools, because `force_tool` is read straight from the payload.

    No capability is granted either way: the interceptor still injects tenancy from verified
    claims, Cedar still decides, and the tool still re-checks ownership. What forcing grants is the
    *choice* of which tool a turn invokes, and that is not the client's to make.
    """
    agent = FakeAgent()
    assert SEARCH in tool_choice._tool_names(TOOLS), "the fixture must offer the tool it refuses"
    assert tool_choice.force(agent, SEARCH, TOOLS) is False
    assert agent._middleware_registry.added == [], (
        "a tool outside the forceable set must install nothing"
    )


def test_the_forceable_set_matches_what_the_bff_can_send():
    """Neither set may grow without the other.

    A tool added to the BFF's registry and not here would be refused at the runtime — the click
    degrading to the stall the forcing exists to remove. One added here and not there would widen
    the seam this closes for nothing. Asserted as equality, so it fails in both directions.
    """
    root = Path(__file__).parents[2]
    for path in (str(root / "conversation-api" / "app"), str(root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from actions import FORCED_TOOLS

    assert set(FORCED_TOOLS.values()) == set(tool_choice.FORCEABLE), (
        "the BFF's forced tools and the agent's forceable set have drifted"
    )


def test_unknown_tool_installs_nothing():
    """A name the turn does not offer must degrade to no forcing, never to a broken request.

    Bedrock rejects a `toolChoice` naming an absent tool by failing the whole call, so a drift
    between
    the BFF's registry and the gateway's target names would turn every write click into an error
    rather
    than into the stall it was fixing.
    """
    agent = FakeAgent()
    assert tool_choice.force(agent, "booking___does_not_exist", TOOLS) is False
    assert agent._middleware_registry.added == [], (
        "nothing may be installed when the name is unusable"
    )


def test_first_call_is_forced():
    if not HAVE_MIDDLEWARE:
        return
    agent, handler = _installed()
    out = asyncio.run(handler(_context(agent, USER_TURN)))
    assert out.tool_choice == {"tool": {"name": PREPARE}}


def test_tool_result_turn_is_not_forced():
    """The guard against an infinite loop, which is the failure this test file exists for.

    After the tool returns, the event loop calls the model again so it can narrate the result.
    Forcing
    that call means calling the tool again, and again — a turn that never ends and bills for every
    lap.
    """
    if not HAVE_MIDDLEWARE:
        return
    agent, handler = _installed()
    out = asyncio.run(handler(_context(agent, TOOL_LOOP)))
    assert out.tool_choice is None


def test_existing_choice_wins():
    """Structured output's own `tool_choice` is a stronger claim on the call than a click's."""
    if not HAVE_MIDDLEWARE:
        return
    agent, handler = _installed()
    existing = {"any": {}}
    out = asyncio.run(handler(_context(agent, USER_TURN, existing)))
    assert out.tool_choice is existing


def test_context_is_copied():
    """The handler must return a new context, never mutate the one it was handed.

    `InvokeModelContext`'s collection fields are defensive copies of agent state, so mutating them
    in
    place is not immediately visible — which is exactly why it is worth asserting.
    """
    if not HAVE_MIDDLEWARE:
        return
    agent, handler = _installed()
    context = _context(agent, USER_TURN)
    out = asyncio.run(handler(context))
    assert context.tool_choice is None
    assert out is not context


def test_empty_conversation_is_not_forced():
    """No messages means no user ask, so there is nothing a click could be forcing."""
    if not HAVE_MIDDLEWARE:
        return
    agent, handler = _installed()
    out = asyncio.run(handler(_context(agent, [])))
    assert out.tool_choice is None


def test_bff_registry_names_match_the_gateway():
    """Every tool the BFF can force must be one the gateway actually exposes.

    The two live in different services and different languages of configuration — `actions.py` and
    `agentcore.json` — so drift is silent: the click keeps working on phrasing alone and the forcing
    quietly stops. Checked here because it is a *static* agreement, and the only cheap place to
    catch it.
    """
    root = Path(__file__).parents[2]
    # `actions` imports `shared.cards`, so the repo root goes on the path as well as the BFF's app
    # directory. Getting this wrong is how the check silently became a no-op the first time it ran:
    # `ImportError` was caught and the test reported `ok` having asserted nothing, which is worse
    # than
    # a failure because it looks like coverage.
    for path in (str(root / "conversation-api" / "app"), str(root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from actions import FORCED_TOOLS

    assert FORCED_TOOLS, "the forced-tool registry is empty, so nothing on the write path is forced"

    spec = Path(__file__).parents[1] / "MultiTenantTravel" / "agentcore" / "agentcore.json"
    config = spec.read_text()
    for action, name in FORCED_TOOLS.items():
        assert name in config, f"{action} forces {name}, which agentcore.json does not declare"


if __name__ == "__main__":
    if not HAVE_MIDDLEWARE:
        print("strands middleware seam unavailable — install strands-agents >= 1.50.2")
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        else:
            print(f"ok   {name}")
    print("\nall passed" if not failures else f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
