"""The part that needs a deployment: log in as a persona and run one turn.

Kept deliberately thin. Everything that decides anything — scoring, aggregation, the gate — is pure
and tested offline, so this module is only plumbing, and plumbing is the right place for the code
that cannot be exercised without an account.

**The login flow is reused, not reimplemented.** `scripts/verify_conversation_api.py` already does
server-side PKCE through the real hosted UI, and a second copy of that would be a second thing to
keep working against a Cognito change. Importing it reads SSM at import time, which is fine here:
this module cannot function without AWS anyway.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for path in (str(REPO_ROOT / "scripts"), str(REPO_ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

import boto3  # noqa: E402
import deployed_refs  # noqa: E402
import verify_conversation_api as conv  # noqa: E402

# **Must match `MODEL_ID` in `agent/.../model/load.py`.** Stated here rather than imported because
# that module pulls in Strands, which this package does not depend on — the same trade the repo
# makes elsewhere for values crossing a package boundary. A test asserts the two literals agree,
# so the duplication cannot drift silently.
MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Long enough for a booking chain across several tool calls; the measured long turn was ~26s.
TURN_TIMEOUT_SECONDS = 180

# **Retries only a stream that carried nothing, and nothing else.**
#
# A full gate run of 51 turns produced three whose connection closed after "0 bytes and 0
# frames", while the relay logged `200 OK` for every one of them — the turns ran, the bytes
# never arrived. All three passed on an immediate re-run. Scored as they stood they read as
# three behavioural failures (a missing verdict card, a missing cancellation card, an
# unmentioned figure) and failed the gate on rows that were fine.
#
# That is the one failure a regression gate must not have. A row that fails on transport
# noise blames whichever commit happened to be running, which is worse than having no row:
# it teaches everyone to re-run until green, and a gate people re-run until it passes is
# not measuring anything.
#
# The condition is deliberately narrow. A turn that reaches the model always ends with a
# `done` event, so *no* `done` means no scoreable transcript arrived. Anything that did
# arrive is scored exactly as it came — including a turn that errored, refused, or answered
# wrongly. This retries an absence of evidence, never a verdict.
TURN_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2


class AgentClient:
    """One session per persona, reused across that persona's tasks.

    Reused deliberately: a fresh login per task would add a hosted-UI round trip to every one of 58
    turns, and the session is not what the fixtures are testing. It also keeps the prompt cache warm
    across a persona's runs, which is where most of the cost saving in a run comes from.
    """

    model_id = MODEL_ID

    def __init__(self) -> None:
        self.api_url = conv.parameters()[conv.API_URL_PARAM]
        self.password = conv.refs.demo_password
        self._cookies: dict[str, str] = {}
        self._travelers: dict[str, str] = {}
        self._tenants: dict[str, str] = {}

    def _session(self, persona: str) -> str:
        if persona not in self._cookies:
            browser = conv.Browser()
            cookie = conv.establish_session(
                browser, self.api_url, persona, self.password, quiet=True
            )
            if not cookie:
                raise RuntimeError(f"could not sign in as {persona}")
            self._cookies[persona] = cookie
        return self._cookies[persona]

    def turn(
        self,
        *,
        persona: str,
        prompt: str,
        scenarios: set[str] | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run one turn and return the typed events, in order.

        Reads the SSE stream to completion rather than sampling it: the evaluators need the whole
        transcript, and the timing questions the conversation-API suite asks are its own concern.

        `scenarios` arms simulated backend conditions for this turn only — see `_arm`.
        """
        events: list[dict[str, Any]] = []
        for attempt in range(1, TURN_ATTEMPTS + 1):
            events = self._attempt(
                persona=persona, prompt=prompt, scenarios=scenarios, tenant_id=tenant_id
            )

            # A `done` event closes every turn that reached the model, so its absence means no
            # scoreable transcript arrived. An HTTP error *is* a result and is returned as one: the
            # run record should say the API refused rather than quietly retrying past it.
            if any(event.get("type") in ("done", "error") for event in events):
                return events
            if attempt < TURN_ATTEMPTS:
                print(f"     (empty stream, retrying: attempt {attempt + 1} of {TURN_ATTEMPTS})")
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        # Reported rather than raised. Three empty streams in a row is an environment that cannot be
        # measured, and inventing a verdict for it would be the same mistake as scoring the first
        # one.
        print(f"     (no usable stream after {TURN_ATTEMPTS} attempts)")
        return events

    def _traveler_id(self, persona: str) -> str:
        """This persona's traveller id, read from the deployment rather than restated.

        `GET /auth/session` returns it for the signed-in session, which is the same value the
        conversation API hashes into the runtime session id. Asking beats importing the seed —
        that pulls pydantic into a package which does not depend on it — and beats a hardcoded
        table, which a re-seed would silently invalidate.
        """
        if persona not in self._travelers:
            request = urllib.request.Request(
                f"{self.api_url}auth/session",
                headers={"Cookie": f"{conv.COOKIE_NAME}={self._session(persona)}"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read())
            traveler_id = body.get("traveler_id")
            if not traveler_id:
                raise RuntimeError(f"no traveler_id for {persona}: {body}")
            self._travelers[persona] = traveler_id
            # Cached from the same response, because the session-id derivation needs it too and
            # asking twice for one payload invites the two halves to disagree.
            self._tenants[persona] = body.get("tenant_id") or ""
        return self._travelers[persona]

    def _tenant_of(self, persona: str) -> str:
        """This persona's tenant, from the same `/auth/session` payload as the traveller."""
        if persona not in self._tenants:
            self._traveler_id(persona)
        return self._tenants[persona]

    def _runtime_session_id(self, persona: str, conversation_id: str) -> str:
        """The session id the *tools* see, which is not the conversation id.

        **Must match `_runtime_session_id` in `conversation-api/app/main.py` exactly**, because that
        is the value the backend reads a scenario row by. The conversation API never passes the
        browser's conversation id through: it hashes it together with the verified traveller, so the
        same conversation id presented by two travellers resolves to two different sessions and
        neither can name the other's.

        Keying a scenario on the conversation id instead looked correct and armed nothing — the row
        was written, no request ever matched it, and every drift task passed by behaving normally.
        Which is the exact failure suite G exists to catch, arrived at from the other direction.

        The traveller id is read from the live session, so a re-seeded fixture cannot silently break
        arming.

        **The tenant is in the hash as of Aug 2026**, matching the API. It was added there as
        defence in depth — traveller ids are globally unique, so nothing collided, but an isolation
        boundary should not rest on a property of the id generator. Both sides moved together
        because `test_gate.py` asserts the derivation against the API's own source, and it caught
        this.
        """
        traveler_id = self._traveler_id(persona)
        tenant_id = self._tenant_of(persona)
        return hashlib.sha256(f"{tenant_id}:{traveler_id}:{conversation_id}".encode()).hexdigest()

    def _arm(self, tenant_id: str, session_id: str, scenarios: set[str]) -> None:
        """Arm simulated backend conditions for exactly this conversation.

        **Written to storage rather than sent as a header, and that is deliberate.** The mock TMC
        is publicly reachable and asks only for a tenant header, so a header switch would let
        anyone put the deployed demo into "every search times out". Arming is instead a DynamoDB
        write by something that already holds AWS credentials, scoped to one session, with a TTL.

        Keyed on the *runtime* session id, not the conversation id — see `_runtime_session_id`.
        Re-armed per attempt, because a retry starts a new conversation and therefore a new session.
        """
        # The offers table is the TTL'd store the backend already reads scenarios from;
        # `INFRA_STACK` is the table prefix the CDK app uses.
        table = f"{deployed_refs.INFRA_STACK}-offers"
        boto3.resource("dynamodb", region_name=deployed_refs.REGION).Table(table).put_item(
            Item={
                "pk": f"TENANT#{tenant_id}",
                "sk": f"SCENARIO#{session_id}",
                "ttl": int(time.time()) + 1800,
                "scenarios": sorted(scenarios),
            }
        )

    def _attempt(
        self,
        *,
        persona: str,
        prompt: str,
        scenarios: set[str] | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """One POST, read to completion. Transport only — the retry policy lives in `turn`."""
        cookie = self._session(persona)
        conversation_id = conv.uuid.uuid4().hex + "aaa"  # >= 33 chars, the runtime's contract
        if scenarios and tenant_id:
            self._arm(tenant_id, self._runtime_session_id(persona, conversation_id), scenarios)
        request = urllib.request.Request(
            f"{self.api_url}conversation/{conversation_id}/messages",
            data=json.dumps({"prompt": prompt}).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Cookie": f"{conv.COOKIE_NAME}={cookie}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TURN_TIMEOUT_SECONDS) as response:
                _, payload, _ = conv._frame_arrivals(response)
        except urllib.error.HTTPError as error:
            return [{"type": "error", "message": f"HTTP {error.code}: {error.read()[:200]!r}"}]

        return _parse_sse(payload)


def _parse_sse(payload: bytes) -> list[dict[str, Any]]:
    """`data:` lines into event dicts.

    An unparseable line is dropped rather than raised on: a malformed frame should cost one event,
    not the task — and the evaluators already treat a missing card or outcome as a failure, which is
    the right verdict for a stream that arrived broken.
    """
    events: list[dict[str, Any]] = []
    for line in payload.decode(errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        try:
            event = json.loads(line[5:])
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events
