"""Where the agent runtime and memory live — resolved from SSM, not from a remembered env var.

**This exists because the alternative failed silently.** The runtime ARN and memory id belong to the
AgentCore CLI's own CloudFormation stack, which deploys *after* this one, so they cannot be
CloudFormation references. They used to be passed in as `TRAVEL_RUNTIME_ARN` / `TRAVEL_MEMORY_ID`
environment variables of the `cdk deploy` command — which meant a redeploy from a shell that had not
exported them **overwrote a working configuration with an empty string**.

Nothing failed at deploy time. The stack updated cleanly, CloudFormation reported success, and the
next traveller to send a message got a `404 <UnknownOperationException/>` from
`InvokeAgentRuntime` — verified by calling it with an empty ARN. That error names no cause, appears
in no deploy log, and points at the wrong layer entirely.

So the value now comes from Parameter Store, which is where every other cross-stack value in this
sample already comes from (`/multi-tenant-travel/backend/api-url`,
`/multi-tenant-travel/guardrails/*`, `/multi-tenant-travel/model/inference-profile-arn`). The
properties that matter:

* **A deploy cannot erase it.** The parameter is written by `scripts/publish_agent_refs.py` from the
  agent stack's own outputs, so it survives any number of `cdk deploy` runs from any shell.
* **A missing value is loud and names the fix**, rather than surfacing as a 404 from a service the
  reader has no reason to suspect.
* **The env var still wins when set**, so a local run or a deliberate experiment can pin a different
  runtime without touching Parameter Store — the same precedence `model/load.py` uses for
  guardrails.

Read once per container: these change only on a deploy, and a parameter read per turn would add
latency to the conversational path for a constant.
"""

from __future__ import annotations

import logging
import os

import boto3

log = logging.getLogger("travel.conversation")

REGION = os.environ.get("AWS_REGION", "us-east-1")

RUNTIME_ARN_VAR = "RUNTIME_ARN"
MEMORY_ID_VAR = "MEMORY_ID"

RUNTIME_ARN_PARAM = "/multi-tenant-travel/agent/runtime-arn"
MEMORY_ID_PARAM = "/multi-tenant-travel/agent/memory-id"

_ssm = None
# `None` means "not looked up yet"; a resolved absence is cached as `""` so a missing
# parameter costs one call per container rather than one per request.
_cache: dict[str, str] = {}


class AgentNotDeployed(RuntimeError):
    """The agent runtime is not reachable because nothing has published its ARN.

    A distinct type so the request handler can answer 503 with an explanation instead of letting an
    empty ARN reach AgentCore and returning its 404 — which is the failure this module exists to
    prevent being confusing.
    """


def _client():
    global _ssm
    if _ssm is None:
        _ssm = boto3.client("ssm", region_name=REGION)
    return _ssm


def _resolve(env_var: str, parameter: str) -> str:
    """The env var if set, else the SSM parameter, else empty. Cached per container."""
    override = os.environ.get(env_var)
    if override:
        return override

    if parameter in _cache:
        return _cache[parameter]

    try:
        value = _client().get_parameter(Name=parameter)["Parameter"]["Value"]
    except Exception as error:  # noqa: BLE001 — any failure means "not configured"
        # Not fatal here. The caller decides: an absent runtime is a 503 on the next turn, while an
        # absent memory id is a legitimately empty history.
        log.warning("could not read %s from SSM (%s)", parameter, type(error).__name__)
        value = ""

    _cache[parameter] = value
    return value


def runtime_arn() -> str:
    """The agent runtime to invoke. Raises `AgentNotDeployed` if nothing has published one.

    **Raising beats returning empty**, because an empty ARN is accepted by boto3 and rejected by the
    service as a 404 that mentions neither the ARN nor this deployment. One clear exception here
    replaces a confusing error two layers away.
    """
    found = _resolve(RUNTIME_ARN_VAR, RUNTIME_ARN_PARAM)
    if not found:
        raise AgentNotDeployed(
            f"no agent runtime configured: {RUNTIME_ARN_PARAM} is unset in Parameter Store and "
            f"{RUNTIME_ARN_VAR} is not in the environment. Deploy the agent "
            "(`agentcore deploy`), then run `scripts/publish_agent_refs.py`."
        )
    return found


def memory_id() -> str:
    """The AgentCore Memory holding conversation history, or `''` if none is configured.

    Empty rather than raising, and that asymmetry with `runtime_arn` is deliberate: without a
    runtime the product does not work, while without memory the history sidebar is simply empty —
    which is also what a brand-new traveller legitimately sees.
    """
    return _resolve(MEMORY_ID_VAR, MEMORY_ID_PARAM)
