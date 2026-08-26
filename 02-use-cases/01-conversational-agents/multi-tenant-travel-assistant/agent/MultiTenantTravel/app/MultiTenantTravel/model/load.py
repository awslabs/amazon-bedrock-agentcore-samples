"""Model selection and the content guardrail attached to it.

The id lives here alone, so nothing else in the agent learns a model id. Swapping the
constant for a read of a versioned SSM model policy (`mode`, tiers, rates) is a change to
this file only — that is the point of the seam.
"""

from __future__ import annotations

import logging
import os

from strands.models.bedrock import BedrockModel

log = logging.getLogger(__name__)

MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Written by `infra/lib/model-attribution.ts`. **Must match `MODEL_PROFILE_PARAM` there** — they cross
# a repo boundary, so the name is stated in both places.
MODEL_PROFILE_PARAM = "/multi-tenant-travel/model/inference-profile-arn"

GUARDRAIL_ID_VAR = "GUARDRAIL_ID"
GUARDRAIL_VERSION_VAR = "GUARDRAIL_VERSION"

# Written by the `Guardrails` construct. **Must match `infra/lib/guardrails.ts`** — they cross
# a repo boundary, so both sides name them explicitly.
GUARDRAIL_ID_PARAM = "/multi-tenant-travel/guardrails/guardrail-id"
GUARDRAIL_VERSION_PARAM = "/multi-tenant-travel/guardrails/guardrail-version"

_resolved: tuple[str | None, str | None] | None = None
_profile_arn: str | None = None
_profile_looked_up = False


def _inference_profile() -> str | None:
    """The application inference profile ARN, or `None` to fall back to the raw model id.

    **Why invoke a profile at all: it is the only way model spend becomes attributable.** An on-demand
    call to a raw model id carries no tags, so every request in the account collapses into one
    undifferentiated Bedrock line item — the infrastructure could be tagged to the component while
    tokens, the expensive half, stayed anonymous. A profile is a resource we own, that we invoke
    *instead of* the model, and that can be tagged.

    Verified rather than assumed: `copyFrom` accepts the `global.` cross-region profile (it is
    `SYSTEM_DEFINED` with a real ARN), and Strands' `BedrockModel` takes the profile ARN as `model_id`
    with no other change.

    **Absent is a warning, not a failure.** A missing parameter costs attribution, not answers — and
    refusing to start would trade a working assistant for a tidier bill. Logged loudly because
    unattributed spend is invisible by nature: nothing else will notice.

    Cached per container: the ARN changes only on a deploy, and a parameter read per turn would put an
    SSM call on the conversational path for a constant.
    """
    global _profile_arn, _profile_looked_up
    if _profile_looked_up:
        return _profile_arn
    _profile_looked_up = True
    try:
        import boto3

        ssm = boto3.client("ssm")
        _profile_arn = ssm.get_parameter(Name=MODEL_PROFILE_PARAM)["Parameter"]["Value"]
    except Exception as error:  # noqa: BLE001 - see the docstring: never fatal
        log.warning(
            "no inference profile at %s (%s) — invoking the model directly, so this spend will "
            "not be attributable in Cost Explorer",
            MODEL_PROFILE_PARAM,
            type(error).__name__,
        )
        _profile_arn = None
    return _profile_arn


def _from_ssm() -> tuple[str | None, str | None]:
    """The guardrail id and version as CDK last published them.

    **SSM rather than a hand-copied env var, because the failure mode of copying is silent.**
    A numbered version has to be pinned (`DRAFT` would let an unreviewed edit take effect with
    no deploy), but pinning it *by hand* in `agentcore.json` means a human moves a number from
    a CDK output into a second repo after every policy change — and if they forget, the agent
    keeps enforcing the old version while deploys stay green. Reading the parameter makes CDK
    the single source of truth: it owns the version, SSM publishes it, this resolves it.

    Cached per container: the value changes only on a deploy, and a parameter read per turn
    would add latency to the conversational path for a constant.
    """
    global _resolved
    if _resolved is not None:
        return _resolved

    try:
        import boto3

        ssm = boto3.client("ssm")
        found = {
            p["Name"]: p["Value"]
            for p in ssm.get_parameters(Names=[GUARDRAIL_ID_PARAM, GUARDRAIL_VERSION_PARAM])[
                "Parameters"
            ]
        }
        _resolved = (found.get(GUARDRAIL_ID_PARAM), found.get(GUARDRAIL_VERSION_PARAM))
    except Exception as error:  # noqa: BLE001 - see below
        # Never fatal. The guardrail is a backstop, so an unreachable parameter store must not
        # take the agent down — but it is logged at WARNING because running unguarded while
        # looking healthy is the outcome to avoid.
        log.warning("could not read guardrail parameters from SSM: %s", error)
        _resolved = (None, None)
    return _resolved


def _guardrail_config() -> dict[str, object]:
    """Guardrail arguments for `BedrockModel`, or nothing if none is configured.

    **Absent is a warning, not a failure.** This guardrail is a backstop: PII is curated away
    at the tool boundary and the refusal rules are in the system prompt, so the agent is
    still correct without it. Refusing to start would trade a real outage for a missing
    secondary control. It is logged loudly, though — a silently unguarded agent that looks
    healthy is exactly the failure a reader of this sample should not inherit.
    """
    # Env vars win when set, so a local run or a deliberate experiment can pin a specific
    # version without touching SSM. Absent them — the deployed path — SSM is the source.
    guardrail_id = os.environ.get(GUARDRAIL_ID_VAR)
    version = os.environ.get(GUARDRAIL_VERSION_VAR)
    if not guardrail_id or not version:
        from_ssm = _from_ssm()
        guardrail_id = guardrail_id or from_ssm[0]
        version = version or from_ssm[1]

    if not guardrail_id or not version:
        log.warning(
            "no guardrail configured (%s/%s unset and %s unreadable) — model input and "
            "output are unfiltered",
            GUARDRAIL_ID_VAR,
            GUARDRAIL_VERSION_VAR,
            GUARDRAIL_ID_PARAM,
        )
        return {}

    return {
        "guardrail_id": guardrail_id,
        # A pinned numbered version, never DRAFT: DRAFT would change what the model may say
        # the moment someone edited the guardrail, with no deploy and nothing in the ledger
        # to mark that behaviour moved.
        "guardrail_version": version,
        # Assessments come back in the response trace, which is what lets a blocked turn be
        # logged with the category that fired rather than as an opaque refusal.
        "guardrail_trace": "enabled",
        # **The consequential one.** It wraps only the last *user text* message in
        # `guardContent`, and Bedrock's documented rule is that once any block is tagged,
        # the other policies evaluate *only* tagged content. Without this, every tool result
        # in the turn — retrieved policy prose, profile records, documents we wrote — is
        # screened as though the traveller had typed it: a false-positive source, and a
        # guardrail charge per turn to inspect our own text.
        "guardrail_latest_message": True,
        # Redact the model's own output when a filter fires, so a partially streamed answer
        # cannot survive in the transcript. Input redaction is left at the SDK default (on):
        # a blocked prompt should not persist verbatim in conversation history either.
        "guardrail_redact_output": True,
        "guardrail_redact_output_message": (
            "I'd rather not answer that, because I couldn't do it safely."
        ),
    }


def load_model() -> BedrockModel:
    """The Bedrock client: the inference profile when one is published, the model id otherwise."""
    config = _guardrail_config()
    if config:
        log.info(
            "guardrail %s version %s attached to model invocation",
            config["guardrail_id"],
            config["guardrail_version"],
        )
    target = _inference_profile() or MODEL_ID
    log.info(
        "invoking %s", "inference profile (tagged)" if target != MODEL_ID else "model id (untagged)"
    )
    return BedrockModel(model_id=target, **config)


def guardrail_id() -> str | None:
    """The guardrail in force, for the ledger. `None` means the model is unguarded.

    Resolved the same way `load_model` resolves it, not read straight from the environment: a
    ledger that reported `None` while a guardrail was actually applied would make every audit
    of "was this turn filtered?" wrong in the safe-looking direction.
    """
    return os.environ.get(GUARDRAIL_ID_VAR) or _from_ssm()[0]


def model_id(model: BedrockModel | None = None) -> str:
    """The **model** in use, for the ledger — never the profile ARN.

    A profile is a billing wrapper, not a model: recording its ARN here would make every per-model
    cost comparison in the ledger compare one value against itself, and a model upgrade would be
    invisible because the ARN does not change. The ledger answers "which model, at what token cost";
    the profile answers "whose budget" — different questions, and conflating them loses the first.

    `BedrockModel` exposes no `.model_id` attribute — it is inside `get_config()`, so
    `getattr(model, "model_id", "unknown")` silently records "unknown" and quietly breaks
    per-model cost attribution. Read through the config, fall back to the constant.
    """
    if model is not None:
        config = model.get_config()
        found = config.get("model_id") if isinstance(config, dict) else None
        # An ARN means the profile is in use; the constant is the model behind it.
        if found and not str(found).startswith("arn:"):
            return str(found)
    return MODEL_ID
