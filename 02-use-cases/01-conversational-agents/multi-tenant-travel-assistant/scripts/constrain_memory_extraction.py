"""Stop AgentCore Memory recording tenant policy as a traveller preference.

    cd backend && uv run python ../scripts/constrain_memory_extraction.py

**The defect this closes, found by the eval suite rather than by reading code.** Two travellers
asked
the identical question — "what is my hotel nightly cap?" — and both answered correctly, but one
never
called `get_travel_policy`. One step, no tool, and prose carrying the cap, the star limit *and* the
breakfast rule. The other took two steps and called the tool.

The difference was history. `USER_PREFERENCE` extraction had written this into the first traveller's
namespace over months of prior sessions:

    "Has a hotel nightly cap of $250.00 USD, can book hotels up to 4 stars, and is eligible for
     breakfast reimbursement when not included in the room rate, per their company (globex) travel
     policy."

That is a **tenant policy stored as a personal preference**, and retrieval then behaves perfectly: a
question about hotel caps matches a record about hotel caps, it enters context, and the model has no
reason to call a tool for something already in front of it. The stored copy is also a snapshot —
lower
the tenant's cap and this traveller keeps being told the old one, with no tool call to correct it.

`memory.py` had already argued this risk and declined the `SEMANTIC` strategy because of it — *"a
semantic record saying 'the cap is $250' survives a policy change that `get_travel_policy` would
have
reported correctly"*. The reasoning was right and the guard was on the wrong strategy:
`USER_PREFERENCE` needed it too, because "what this person prefers" and "what their employer
permits"
are indistinguishable to an extractor reading conversation text.

**Why this is a script and not two lines of `agentcore.json`.** Two hard constraints, both
discovered
by trying:

1. The CLI's spec schema for strategies is `z.enum(["SEMANTIC","SUMMARIZATION","USER_PREFERENCE",
   "EPISODIC"])`, declared `.strict()`. There is no `CUSTOM` type and nowhere to put an override, so
   the spec cannot express this at all.
2. `UpdateMemory` refuses to reconfigure a built-in one: *"Configuration updates are not allowed for
   memory strategy type USER_PREFERENCE"*. An override is only ever created, never added later.

So the built-in strategy is **replaced** by a `CUSTOM` strategy carrying the same namespace and an
extraction override. The namespace is what matters for correctness: `memory.py` retrieves by
namespace
path, never by strategy id or name, so the swap is invisible to the agent.

**This fixes writes only.** Deleting a strategy does *not* delete its records — measured, because
the
opposite is the natural assumption: immediately after the swap the old strategy was absent from
`GetMemory` while all ten of its records were still present, still stamped with its id, and still
returned by semantic retrieval (the policy record came back top at 0.759 against a 0.3 floor). So
`purge_orphaned_preferences.py` is a required second step, not a tidy-up. `deploy.sh` runs both.

Idempotent and resumable, so `deploy.sh` can run it every time and a run that dies between the
delete
and the add recovers on the next one.
"""

from __future__ import annotations

import json
import sys
import time

import boto3
from botocore.exceptions import ClientError
from deployed_refs import refs

# Must match the strategy `name` in `agent/MultiTenantTravel/agentcore/agentcore.json`, and
# `PREFERENCES_NAMESPACE` in `agent/.../memory.py`. All three cross a repo boundary, so each is
# stated in place; a mismatch surfaces as retrieval returning nothing rather than as an error.
STRATEGY_NAME = "TravelPreferences"
NAMESPACE_TEMPLATE = "/travel/preferences/{actorId}/"
DESCRIPTION = "Observed travel preferences the profile record does not hold"

# Cheap and deterministic enough for a classification this narrow. Extraction runs asynchronously
# after a turn, so it is off the conversational path and latency is not the constraint — but a small
# model is the right default for "does this sentence describe a rule or a habit?".
#
# The inference-profile form (`us.`) rather than the bare foundation-model id: Haiku 4.5 is served
# through cross-region profiles, and `list-inference-profiles` reports `us.` and `global.` for it.
EXTRACTION_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Named so a reader of the console can tell why it exists and what deleting it would break.
GRANT_POLICY_NAME = "ConstrainedExtractionModelAccess"

# **Criteria, not output format.** The override appends to the built-in prompt, which already knows
# the record shape; what it does not know is that this domain has facts a tool owns.
APPEND_TO_PROMPT = """
ADDITIONAL EXCLUSION RULES FOR THIS DOMAIN.

Never extract a corporate travel policy rule as a preference, even when the traveller
discusses it at length, asks about it repeatedly, or expresses an opinion about it. These
are facts owned by the employer and served by a tool, and a stored copy goes stale the
moment the employer changes it.

Specifically, do NOT extract:
- hotel nightly caps, or any monetary limit, and any currency attached to one
- hotel star-rating limits
- cabin-class entitlements or the rules that earn them, including trip-count thresholds
- advance-purchase windows or booking-deadline rules
- whether a fare is refundable, or reimbursement and expense rules
- any statement of the form "the traveller is permitted / entitled / limited to ..."

Never extract a specific trip, itinerary or plan as a preference. "Planning to travel to
Berlin on 29 August", "travelling to Amsterdam 5-8 December", a named hotel booking or a
flight on a date are all itinerary facts owned by the trips tool, and they are transient:
the trip happens and the record stays, so a later conversation is told about travel that
is over or was never booked. Specifically do NOT extract:
- a destination together with dates, or "planning to travel to X"
- a particular booking, reservation or confirmation
- anything phrased "as of <date>" or "currently"

DO extract genuine personal preferences, which are the traveller's own and which no tool
holds:
- preferred airlines, hotel chains, seat position, room type
- habits such as consistently choosing the cheapest option, or wanting breakfast included
- practical needs such as electric-vehicle charging, accessibility, dietary requirements
- communication preferences, such as wanting detailed explanations rather than brief ones

The distinction to apply: a preference describes what this person would choose. A policy
describes what their employer allows. If a statement would change when the employer
changed its rules — and not when the traveller changed their mind — it is a policy, and
you must not extract it.
""".strip()

OVERRIDE = {
    "userPreferenceOverride": {
        "extraction": {"appendToPrompt": APPEND_TO_PROMPT, "modelId": EXTRACTION_MODEL}
    }
}


def grant_model_access(role_arn: str) -> None:
    """Let the memory execution role invoke the extraction model.

    **Not optional, and not obvious.** A built-in strategy needs no permissions at all — this role
    ships with *zero* policies, because AgentCore extracts with a service-managed model. The moment
    a
    custom `modelId` is named the invocation becomes the customer's, and the call fails with
    `AccessDeniedException: Role does not have access for the specified model`. That message names
    the
    role nowhere, so it reads like a bad model id.

    **`InvokeModel`, not `Converse`** — the same finding the runtime role documents: Converse
    authorizes against the invoke actions, and a policy listing `bedrock:Converse` denies
    everything.

    **Region-wildcarded resources** for the same reason as the runtime role: a cross-region
    inference
    profile fronts underlying model ARNs in *other* regions, so pinning this region would refuse the
    very model being configured.
    """
    iam = boto3.client("iam")
    role_name = role_arn.rsplit("/", 1)[-1]
    document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-*",
                    f"arn:aws:bedrock:*:{refs.account}:inference-profile/{EXTRACTION_MODEL}",
                ],
            }
        ],
    }

    try:
        current = iam.get_role_policy(RoleName=role_name, PolicyName=GRANT_POLICY_NAME)
        if current["PolicyDocument"] == document:
            print(f"  model access already granted to {role_name}")
            return
    except iam.exceptions.NoSuchEntityException:
        pass

    iam.put_role_policy(
        RoleName=role_name, PolicyName=GRANT_POLICY_NAME, PolicyDocument=json.dumps(document)
    )
    print(f"  granted {EXTRACTION_MODEL} to {role_name}")


def wait_active(control, memory_id: str, *, timeout: int = 300) -> dict:
    """Block until the memory leaves its modifying state, and return it.

    Strategy changes are asynchronous. Issuing the `add` while the `delete` is still settling fails
    with a conflict, which on a first run reads like the add itself being wrong.
    """
    deadline = time.time() + timeout
    while True:
        memory = control.get_memory(memoryId=memory_id)["memory"]
        status = memory.get("status")
        if status == "ACTIVE":
            return memory
        if status == "FAILED":
            raise SystemExit(f"{memory_id} is FAILED: {memory.get('failureReason')}")
        if time.time() > deadline:
            raise SystemExit(f"{memory_id} still {status} after {timeout}s")
        time.sleep(5)


def is_constrained(strategy: dict) -> bool:
    """True when this strategy already carries exactly the override below.

    Compared rather than assumed, so a re-run is a no-op: `UpdateMemory` puts the resource into a
    modifying state, and doing that on every deploy would add a wait and a window where extraction
    is
    reconfiguring for no reason.
    """
    extraction = ((strategy.get("configuration") or {}).get("extraction") or {}).get(
        "customExtractionConfiguration"
    ) or {}
    current = extraction.get("userPreferenceExtractionOverride") or {}
    return (
        current.get("appendToPrompt") == APPEND_TO_PROMPT
        and current.get("modelId") == EXTRACTION_MODEL
    )


def main() -> int:
    control = boto3.client("bedrock-agentcore-control", region_name=refs.region)
    memory_id = refs.memory_id

    memory = wait_active(control, memory_id)
    role_arn = memory.get("memoryExecutionRoleArn")
    if not role_arn:
        print(f"{memory_id} has no memoryExecutionRoleArn.", file=sys.stderr)
        return 1
    grant_model_access(role_arn)

    existing = next(
        (s for s in memory.get("strategies") or [] if s.get("name") == STRATEGY_NAME), None
    )

    if existing and is_constrained(existing):
        print(f"  extraction already constrained on {STRATEGY_NAME} ({existing['strategyId']})")
        return 0

    # **Replace, because an override cannot be added to a built-in strategy.** Deleting takes its
    # records with it, which is the point: the policy-as-preference records already written would
    # otherwise keep bypassing the tool no matter how extraction is configured from here.
    if existing:
        # **`namespaces` on read, `namespaceTemplates` on write** — the same field under two names,
        # and
        # reading the write-side name silently yields `None`, which would make this guard pass on a
        # strategy whose namespace had actually drifted.
        namespaces = existing.get("namespaces") or existing.get("namespaceTemplates") or []
        if NAMESPACE_TEMPLATE not in namespaces:
            print(
                f"  refusing to replace: {STRATEGY_NAME} has namespaces {namespaces}, expected "
                f"{NAMESPACE_TEMPLATE!r}. memory.py retrieves by that path — reconcile first.",
                file=sys.stderr,
            )
            return 1
        print(f"  replacing built-in {existing['type']} strategy ({existing['strategyId']})")
        control.update_memory(
            memoryId=memory_id,
            memoryStrategies={
                "deleteMemoryStrategies": [{"memoryStrategyId": existing["strategyId"]}]
            },
        )
        wait_active(control, memory_id)
        print("  built-in strategy and its records removed")

    for attempt in range(6):
        try:
            control.update_memory(
                memoryId=memory_id,
                memoryStrategies={
                    "addMemoryStrategies": [
                        {
                            "customMemoryStrategy": {
                                "name": STRATEGY_NAME,
                                "description": DESCRIPTION,
                                "namespaceTemplates": [NAMESPACE_TEMPLATE],
                                "configuration": OVERRIDE,
                            }
                        }
                    ]
                },
            )
            break
        except ClientError as exc:
            # IAM is eventually consistent: `put_role_policy` returns before the grant is visible to
            # Bedrock, and the failure is the same `AccessDeniedException` a genuinely missing grant
            # gives — so one attempt fails a first-time deploy at random and looks like a bad model
            # id.
            code = exc.response["Error"]["Code"]
            retryable = code in ("AccessDeniedException", "ConflictException")
            if not retryable or attempt == 5:
                raise
            print(f"  waiting for the grant to propagate (attempt {attempt + 1})")
            time.sleep(5)

    memory = wait_active(control, memory_id)
    added = next(
        (s for s in memory.get("strategies") or [] if s.get("name") == STRATEGY_NAME), None
    )
    if not added or not is_constrained(added):
        print(f"  {STRATEGY_NAME} did not come back constrained: {added}", file=sys.stderr)
        return 1

    print(f"  constrained extraction on {STRATEGY_NAME} ({added['strategyId']}, {added['type']})")
    print(f"  policy facts will no longer be stored as preferences (model {EXTRACTION_MODEL})")
    print("  NOTE: existing records survive a strategy delete and are still retrieved — run")
    print("        scripts/purge_orphaned_preferences.py to remove them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
