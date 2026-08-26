"""Test helpers shared by every tool's smoke test.

**Extracted rather than copied per family**, which is the specific drift a nine-family tool layer
is most exposed
to: fourteen tools each hand-rolling a fake Lambda context is fourteen chances to get the *shape*
wrong — and getting it wrong makes a test pass against a structure the Gateway never sends. The
propagated-headers key living in `context.py` and the fake honouring it means the two cannot
disagree.

Not bundled into the Lambda: `infra/lib/tools.ts` deletes `test_*.py` from the asset, and this
module is only imported by those files.
"""

from __future__ import annotations

from typing import Any

from .context import (
    ROLE_HEADER,
    SESSION_HEADER,
    TENANT_HEADER,
    TRAVELER_HEADER,
    RequestContext,
)

# The two seeded tenants. Named here so a test asserting a two-tenant contrast cannot drift from
# the seed data by copying a stale id.
GLOBEX = RequestContext(tenant_id="globex", traveler_id="trv_31d81fa59772", role="traveler")
GLOBEX_ARRANGER = RequestContext(
    tenant_id="globex", traveler_id="trv_95c557b6c43e", role="arranger"
)
INITECH = RequestContext(tenant_id="initech", traveler_id="trv_bbc2e338c41a", role="traveler")


class FakeLambdaContext:
    """Stands in for the Lambda context the Gateway supplies.

    Mirrors the real shape, confirmed by dumping a live invocation: the tool name *and* the
    propagated headers both live in `client_context.custom`, while the event carries only the
    model's arguments. A fake that put identity in the event would let a broken tool pass its test
    and fail in production.
    """

    def __init__(
        self,
        tool_name: str,
        *,
        identity: RequestContext | None = GLOBEX,
        session_id: str | None = "test-session",
    ) -> None:
        custom: dict[str, Any] = {"bedrockAgentCoreToolName": tool_name}
        if identity is not None:
            headers = {
                "Authorization": "Bearer <verified-upstream>",
                TENANT_HEADER: identity.tenant_id,
                ROLE_HEADER: identity.role or "traveler",
            }
            if identity.traveler_id:
                headers[TRAVELER_HEADER] = identity.traveler_id
            if session_id:
                headers[SESSION_HEADER] = session_id
            custom["bedrockAgentCorePropagatedHeaders"] = headers
        self.client_context = type("ClientContext", (), {"custom": custom})()


def ok(label: str, condition: bool, detail: str = "") -> bool:
    """Print one check result. Returns the condition so callers can accumulate."""
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    for line in str(detail).splitlines():
        if line:
            print(f"        {line}")
    return condition


def summarise(results: list[bool]) -> int:
    """Print a tally and return a process exit code."""
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1
