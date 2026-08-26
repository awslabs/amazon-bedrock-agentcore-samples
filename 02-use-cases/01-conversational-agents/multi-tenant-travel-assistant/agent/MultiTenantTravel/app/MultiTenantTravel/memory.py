"""Conversation memory: this conversation's history, and this traveller's learned preferences.

**Two capabilities, one resource, and they are worth separating.**

*Short-term* is within-conversation continuity — what makes "book the first one" mean anything. The
write path is deliberately three turns (search → prepare → confirm) so nothing is booked without an
explicit in-turn confirmation, and that only works if the previous turn is still in context. Scoped
to the session.

*Long-term* is `USER_PREFERENCE` extraction: the aisle seat, the chain someone always picks. Scoped
to the actor, so it outlives any one conversation.

**Only `USER_PREFERENCE`, and the absence of the others is the design.** `SEMANTIC` would extract
general facts from conversation — but facts here come from tools, deterministically, and a semantic
record saying "the cap is $250" survives a policy change that `get_travel_policy` would have reported
correctly. Memory stores what no tool owns: `backend/app/models/traveler.py` holds *declared*
preferences (what someone typed into a form), and nothing holds *observed* ones. That gap is this
strategy's job, and it does not compete with a tool for the same fact.

**The agent holds verified identity here, for the first time, and that is a real change.** Everywhere
else the agent asserts nothing about who is asking — tool-facing tenancy comes from the gateway
interceptor, which the model has no channel to influence. But memory is agent-side: the agent itself
must name the actor. Its source is the bearer token the *runtime* already validated against Cognito
(signature, expiry, `allowedClients`) before this code ran, so this is **reading** a verified claim,
not letting the model choose one. The BFF could not pass the actor in the payload instead — that is
precisely the channel the model can reach.

Verified against the deployed pool: the access token carries `custom:tenant_id` and
`custom:traveler_id` (Cognito puts custom attributes in the *ID* token by default; the
pre-token-generation trigger at `V2_0` is what mirrors them onto the access token), and the runtime's
`requestHeaderAllowlist: ["Authorization"]` is what delivers it here.

**What IAM does and does not bound.** The CLI converts `{actorId}` in a namespace template to `*` for
its `bedrock-agentcore:namespace` conditions, so the runtime's role is scoped to the namespace
*shape* — not to one tenant. The per-traveller boundary is the `actor_id` this module composes, which
is why it is derived from verified claims and never from anything a caller supplied. Stated plainly
because a namespace containing the tenant name looks like an IAM boundary and is not one.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os

from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

log = logging.getLogger(__name__)

REGION_VAR = "AWS_REGION"

# Written onto the runtime by the CLI's own CDK, from the `memories` entry in `agentcore.json`:
# the name is uppercased into `MEMORY_<NAME>_ID`. Not a value we choose — matching it is what makes
# the memory resource discoverable without a hand-copied id.
MEMORY_ID_VAR = "MEMORY_CONVERSATIONS_ID"

# Must match `namespaceTemplates` on the USER_PREFERENCE strategy in `agentcore.json`. They cross a
# repo boundary (TypeScript-generated CDK reads the JSON; this reads the deployed resource), so the
# template is stated in both places and a mismatch surfaces as retrieval returning nothing rather
# than as an error.
PREFERENCES_NAMESPACE = "/travel/preferences/{actorId}/"

# Preferences are few and should be *relevant*: a low `top_k` with a higher floor keeps a stale or
# weakly-matching preference out of the prompt. A preference wrongly injected is worse than one
# missed — it makes the assistant confidently wrong about someone's own habits.
PREFERENCE_TOP_K = 5
PREFERENCE_RELEVANCE = 0.3


def _claims(bearer: str | None) -> dict:
    """Claims from the bearer token, or `{}`.

    **Unverified on purpose**, and safe for one specific reason: the runtime already validated this
    token against Cognito — signature, expiry, `allowedClients` — before invoking us. Re-verifying would
    mean fetching JWKS and doing RS256 here, duplicating a check that has already happened at the
    boundary that counts.
    """
    if not bearer:
        return {}
    try:
        payload = bearer.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except (IndexError, ValueError, binascii.Error):
        log.warning("could not read claims from the bearer token")
        return {}


def identity(bearer: str | None) -> tuple[str | None, str | None]:
    """`(tenant_id, traveler_id)` from the runtime-verified token.

    Exposed separately from `actor_id` because the ledger wants the two dimensions apart while
    memory wants them joined into one namespace path. Same claims, same single reader, so the two
    cannot drift.

    Safe for the same reason the rest of this module is: the runtime validated this token against
    Cognito before invoking us, and the model has no channel to either value.
    """
    claims = _claims(bearer)
    return claims.get("custom:tenant_id"), claims.get("custom:traveler_id")


def actor_id(bearer: str | None) -> str | None:
    """`{tenant}/{traveler}` from the runtime-verified token, or `None`.

    **Slash-separated, and the separator is the service's rather than mine.** `actorId` is validated
    against `[a-zA-Z0-9][a-zA-Z0-9-_/]*(?::[a-zA-Z0-9-_/]+)*[a-zA-Z0-9-_/]*` — so `#` is rejected
    outright, and `/` makes tenant a genuine path segment in the resolved namespace instead of an
    opaque prefix.

    Neither claim can carry a separator: both are Cognito custom attributes marked **immutable** and
    set by the seed, `tenant_id` bounded to 32 characters. So a traveller cannot edit either to
    reshape the namespace.

    Claims are read **without verifying the signature**, which is safe for one specific reason: the
    runtime already validated this token before invoking us. Re-verifying would mean fetching JWKS
    and doing RS256 here, duplicating a check that has already happened at the boundary that counts.
    """
    claims = _claims(bearer)
    tenant = claims.get("custom:tenant_id")
    traveler = claims.get("custom:traveler_id")
    if not tenant or not traveler:
        # A token without these is a pre-token-trigger regression, not a user error. Loud, because
        # the alternative is memory silently writing to a shared actor.
        log.warning(
            "token carries no custom:tenant_id/custom:traveler_id — memory is disabled for this "
            "turn rather than risk a shared actor"
        )
        return None
    return f"{tenant}/{traveler}"


def session_context(bearer: str | None) -> str | None:
    """Who this turn is for, as a post-cache-breakpoint system block.

    **Closes a gap between what the prompt promises and what the agent knows.** `identity.j2` tells the
    model "you already know which employee you are helping" — and until now nothing told it, so a
    greeting had to either stay impersonal or spend a `get_traveler_profile` call to learn a name it
    could have been handed.

    **Free, in cache terms.** This text sits *after* the cache breakpoint (see
    `prompts.manager.system_blocks`), so the stable prefix is still read from cache: measured at 1042
    cached tokens read for three different travellers across two tenants. Variables are fine; variables
    *before* the breakpoint are what destroy a shared prefix.

    **Identity only, never authorization.** Tenant and traveller ids come from the runtime-verified JWT
    — the same source `actor_id` uses — and are stated here so the model can *address* someone, not so
    it can decide anything. Every tool remains scoped by the gateway interceptor from the same token,
    so a model that somehow misread this block still could not reach another tenant's data.

    Deliberately **not** the traveller's name or preferences: those live in the profile, which is a tool
    call away and a system of record. Copying them here would create a second source that goes stale
    mid-conversation, and the ids are what the model actually needs in order to stop asking.
    """
    claims = _claims(bearer)
    tenant = claims.get("custom:tenant_id")
    traveler = claims.get("custom:traveler_id")
    if not tenant or not traveler:
        return None
    role = claims.get("custom:role") or "traveler"
    return (
        "<this_session>\n"
        f"You are helping traveller {traveler} at {tenant}. Their role is {role}.\n"
        "These are established facts, not something to confirm or ask about. Use "
        "`get_traveler_profile` when you need their name or preferences.\n"
        "</this_session>"
    )


def conversation_memory(session_id: str | None, bearer: str | None):
    """A session manager for this conversation, or `None` if memory is unavailable.

    **Absent memory degrades the conversation; it must not end it.** A single-turn question needs no
    history, so a missing resource is logged loudly and the turn proceeds. Refusing to start would
    turn a missing convenience into an outage — and the booking flow's safety does not rest on
    memory: `confirm_booking` re-derives the held offer server-side and re-checks ownership, so a
    forgotten context produces a refusal, never a wrong booking.
    """
    memory_id = os.environ.get(MEMORY_ID_VAR)
    actor = actor_id(bearer)
    if not memory_id or not session_id or not actor:
        log.warning(
            "no conversation memory this turn (memory_id=%s session=%s actor=%s) — multi-turn "
            "flows such as search → prepare → confirm will not carry context",
            bool(memory_id),
            bool(session_id),
            bool(actor),
        )
        return None

    config = AgentCoreMemoryConfig(
        memory_id=memory_id,
        # The runtime session id, which the conversation API derives from the verified traveller and
        # the conversation id together — so a copied conversation id resolves elsewhere and cannot
        # read another traveller's transcript.
        session_id=session_id,
        actor_id=actor,
        # Long-term retrieval. The manager substitutes `{actorId}` from `actor_id` above, so a
        # traveller only ever retrieves their own preferences.
        retrieval_config={
            PREFERENCES_NAMESPACE: RetrievalConfig(
                top_k=PREFERENCE_TOP_K, relevance_score=PREFERENCE_RELEVANCE
            )
        },
        # **Required, because the entrypoint uses `stream_async`.** In async mode the manager offloads
        # its per-turn boto3 calls to a thread; without it those calls block the event loop, which is
        # the same class of bug that made the BFF's relay look like a broken streaming integration.
        async_mode=True,
        # Tool-call blocks are stripped from restored history. The model does not need to re-read its
        # own past tool traffic to know what was decided, and leaving them in spends context on
        # payloads that also carry the most PII of anything in the transcript.
        filter_restored_tool_context=True,
    )

    try:
        return AgentCoreMemorySessionManager(
            config, region_name=os.environ.get(REGION_VAR, "us-east-1")
        )
    except Exception as error:  # noqa: BLE001 - see the docstring: never fatal
        log.warning("could not open conversation memory: %s", error)
        return None
