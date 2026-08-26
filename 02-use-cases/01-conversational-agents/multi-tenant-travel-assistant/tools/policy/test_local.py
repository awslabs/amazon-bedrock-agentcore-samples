"""Standalone smoke test for the policy tool.

    uv run python -m tools.policy.test_local

Runs against the **deployed backend** with no Gateway, no Runtime and no model in
the loop, which is the point: if the two tenants get different correct answers here,
then any later failure is in the identity chain rather than in the tool.
"""

from __future__ import annotations

import os
import sys

from tools.common import RequestContext
from tools.common.context import ROLE_HEADER, TENANT_HEADER, TRAVELER_HEADER

from .handler import get_travel_policy
from .handler import handler as lambda_handler

GLOBEX = RequestContext(tenant_id="globex", traveler_id="trv_31d81fa59772", role="traveler")
INITECH = RequestContext(tenant_id="initech", traveler_id="trv_bbc2e338c41a", role="traveler")


class _FakeLambdaContext:
    """Stands in for the Lambda context the Gateway supplies.

    Mirrors the real shape, confirmed by dumping a live invocation: the tool name *and*
    the propagated headers both live in `client_context.custom`, while the event carries
    only the model's arguments.
    """

    def __init__(self, tool_name: str, *, with_identity: bool = True) -> None:
        custom: dict = {"bedrockAgentCoreToolName": tool_name}
        if with_identity:
            custom["bedrockAgentCorePropagatedHeaders"] = {
                "Authorization": "Bearer <verified-upstream>",
                TENANT_HEADER: "globex",
                TRAVELER_HEADER: "trv_31d81fa59772",
                ROLE_HEADER: "traveler",
            }
        self.client_context = type("ClientContext", (), {"custom": custom})()


def handler(arguments: dict, context: _FakeLambdaContext, *, with_identity: bool = True) -> dict:
    """Invoke the real entry point exactly as the Gateway would.

    The event is the bare argument object — no identity in it, which is the property that
    makes tenancy unforgeable by the model.
    """
    if not with_identity:
        context = _FakeLambdaContext("policy___get_travel_policy", with_identity=False)
    return lambda_handler(dict(arguments), context)


def _cap(response: dict) -> tuple[str, str] | None:
    cap = response.get("facts", {}).get("hotel_nightly_cap")
    return (cap["amount"], cap["currency"]) if cap else None


def main() -> int:
    if not os.environ.get("BACKEND_API_URL"):
        print("set BACKEND_API_URL to the deployed mock TMC base URL")
        return 2

    failures: list[str] = []

    def check(label: str, actual, expected) -> None:
        ok = actual == expected
        print(f"  {'ok  ' if ok else 'FAIL'} {label}: {actual!r}")
        if not ok:
            failures.append(f"{label}: expected {expected!r}, got {actual!r}")

    print("Two tenants, one question — 'what's my hotel cap?'")
    globex = get_travel_policy({"topic": "hotel"}, GLOBEX)
    initech = get_travel_policy({"topic": "hotel"}, INITECH)
    check("globex cap", _cap(globex), ("250.00", "USD"))
    check("initech cap", _cap(initech), ("150.00", "EUR"))
    check("globex stars", globex["facts"].get("max_hotel_star_rating"), 4)
    check("initech stars", initech["facts"].get("max_hotel_star_rating"), 3)

    print("Cabin rules differ, and neither is a verdict")
    g_air = get_travel_policy({"topic": "air"}, GLOBEX)
    i_air = get_travel_policy({"topic": "air"}, INITECH)
    check("globex cabin rule", g_air["facts"]["cabin_rule"]["type"], "trip_count")
    check("globex nth trip", g_air["facts"]["cabin_rule"].get("every_nth_trip"), 4)
    check("initech cabin rule", i_air["facts"]["cabin_rule"]["type"], "never")
    check("initech advance purchase", i_air["facts"].get("advance_purchase_days"), 7)
    check(
        "no verdict leaked into facts",
        any(k in g_air["facts"] for k in ("permitted", "entitled", "verdict")),
        False,
    )

    print("No topic reads everything")
    everything = get_travel_policy({}, GLOBEX)
    check("has hotel cap", "hotel_nightly_cap" in everything["facts"], True)
    check("has cabin rule", "cabin_rule" in everything["facts"], True)
    check("provenance names the tenant", everything["provenance"]["tenant_id"], "globex")

    # Through the real handler, because translating a raised ToolError into a clean
    # `{message}` is `dispatch`'s job — calling the function directly would only
    # prove that it raises, not that the model receives something usable.
    print("Refusals beat invention (via the Gateway entry point)")
    unknown = handler({"topic": "spacecraft"}, _FakeLambdaContext("policy___get_travel_policy"))
    check("unknown topic refuses", "message" in unknown and "facts" not in unknown, True)

    print("A request with no injected tenant returns no data")
    unscoped = handler({}, _FakeLambdaContext("policy___get_travel_policy"), with_identity=False)
    check("refuses without identity", "facts" not in unscoped, True)

    print("The response carries no cards — policy is prose, not tiles")
    check("no cards", "cards" in globex, False)

    if failures:
        print(f"\n{len(failures)} failure(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
