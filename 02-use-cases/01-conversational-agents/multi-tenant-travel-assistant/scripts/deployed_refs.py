"""Resolve deployed identifiers, so no verification script has to hardcode one.

    from deployed_refs import refs
    token = login(refs.user_pool_id, refs.cli_client_id, ...)

Each suite used to open with a block of ids pasted from whichever account was deployed. Pointed at
any other account they do not report a configuration problem — they report a *failing test*, on the
layers this sample exists to demonstrate.

Resolved lazily, so importing costs nothing. The suites then read at *their* import time, which
means `--help` needs a deployment: the tradeoff is deliberate, because `verify_guardrails` is
imported as a library by three suites that never call its `main()`, and resolving there would leave
them with `None`.
"""

from __future__ import annotations

import functools
import os

import boto3

# Not `AWS_REGION` alone, which a shell often carries for unrelated work.
REGION = os.environ.get("TRAVEL_REGION") or os.environ.get("AWS_REGION") or "us-east-1"

INFRA_STACK = "multi-tenant-travel"
AGENT_STACK = "AgentCore-MultiTenantTravel-default"

# Must match `PASSWORD_PARAM` in `backend/seed/users.py`, which writes it. Stated in both places
# rather than imported: the seed is a package under `backend/` and these scripts do not otherwise
# depend on it, and a mismatch surfaces immediately as a missing parameter rather than silently.
DEMO_PASSWORD_PARAM = "/multi-tenant-travel/identity/demo-password"


class DeployedRefs:
    """Identifiers of the live deployment, resolved on first access."""

    @functools.cached_property
    def _ssm(self):
        return boto3.client("ssm", region_name=REGION)

    @functools.cached_property
    def _cfn(self):
        return boto3.client("cloudformation", region_name=REGION)

    @functools.cached_property
    def account(self) -> str:
        return boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]

    @property
    def region(self) -> str:
        return REGION

    def parameter(self, name: str) -> str:
        """One `/multi-tenant-travel/*` parameter. A bare `ParameterNotFound` reads as a typo; it
        means a stack or a post-deploy script has not run."""
        try:
            return self._ssm.get_parameter(Name=name)["Parameter"]["Value"]
        except self._ssm.exceptions.ParameterNotFound:
            raise SystemExit(
                f"{name} not found in {self.account}/{REGION}.\n"
                "Deploy first — `./deploy.sh` publishes every parameter these suites read."
            ) from None

    @functools.cached_property
    def demo_password(self) -> str:
        """The shared demo password, as `seed.users` stored it.

        **The suites read it rather than being handed it.** Passing `--password` on the command line
        puts a credential in shell history and in whatever captured the terminal, and it was easy to
        pass a stale one after a re-seed and read the resulting authentication failure as a broken
        deployment. The flag still works and still wins, for a pool seeded by hand.
        """
        return self._ssm.get_parameter(Name=DEMO_PASSWORD_PARAM, WithDecryption=True)["Parameter"][
            "Value"
        ]

    def stack_output(self, stack: str, needle: str) -> str:
        """One output of `stack` whose key *contains* `needle`.

        Substring rather than prefix: CDK builds a logical id from the construct path plus a hash,
        so `TenantDataRoleArn` inside a `TenantIsolation` construct becomes
        `TenantIsolationTenantDataRoleArn0AE372AF`. Ambiguity is an error — a suite silently
        measuring the wrong resource is worse than one that refuses to run.
        """
        try:
            stacks = self._cfn.describe_stacks(StackName=stack)["Stacks"]
        except self._cfn.exceptions.ClientError:
            raise SystemExit(
                f"stack {stack} is not deployed in {self.account}/{REGION} — run `./deploy.sh`"
            ) from None
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}
        matches = [key for key in outputs if needle in key]
        if len(matches) != 1:
            raise SystemExit(f"{needle!r} matched {len(matches)} outputs in {stack}: {matches}")
        return outputs[matches[0]]

    # --- identity ---------------------------------------------------------------------------

    @functools.cached_property
    def user_pool_id(self) -> str:
        return self.parameter("/multi-tenant-travel/identity/user-pool-id")

    @functools.cached_property
    def cli_client_id(self) -> str:
        """The username/password client. The web client has no password flow, by design."""
        return self.parameter("/multi-tenant-travel/identity/cli-client-id")

    @functools.cached_property
    def web_client_id(self) -> str:
        return self.parameter("/multi-tenant-travel/identity/web-client-id")

    # --- agent ------------------------------------------------------------------------------

    @functools.cached_property
    def runtime_arn(self) -> str:
        """Published by `publish_agent_refs.py` from the agent stack's own outputs."""
        return self.parameter("/multi-tenant-travel/agent/runtime-arn")

    @functools.cached_property
    def memory_id(self) -> str:
        """The conversation memory, published beside the runtime ARN by the same script."""
        return self.parameter("/multi-tenant-travel/agent/memory-id")

    @functools.cached_property
    def gateway_arn(self) -> str:
        return self.stack_output(AGENT_STACK, "GatewayToolsArn")

    @functools.cached_property
    def gateway_mcp_url(self) -> str:
        """Derived rather than stored: the id in the hostname *is* the id in the ARN."""
        gateway_id = self.gateway_arn.rsplit("/", 1)[-1]
        return f"https://{gateway_id}.gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp"

    # --- data plane -------------------------------------------------------------------------

    @functools.cached_property
    def tenant_data_role_arn(self) -> str:
        """The role scoped by `dynamodb:LeadingKeys` and assumed per request with a session tag."""
        return self.stack_output(INFRA_STACK, "TenantDataRoleArn")

    @functools.cached_property
    def backend_api_url(self) -> str:
        """The mock TMC's base URL, including the stage.

        `MockTmcApiUrl` rather than the CDK-generated `MockTmcRestApiEndpoint`: both resolve to the
        same URL, and the named output is the one this repo declared on purpose.
        """
        return self.stack_output(INFRA_STACK, "MockTmcApiUrl")

    @functools.cached_property
    def knowledge_base_id(self) -> str:
        return self.parameter("/multi-tenant-travel/knowledge/knowledge-base-id")

    @functools.cached_property
    def guardrail_id(self) -> str:
        return self.parameter("/multi-tenant-travel/guardrails/guardrail-id")

    @functools.cached_property
    def guardrail_version(self) -> str:
        return self.parameter("/multi-tenant-travel/guardrails/guardrail-version")

    @functools.cached_property
    def site_origin(self) -> str:
        return self.parameter("/multi-tenant-travel/frontend/origin")


refs = DeployedRefs()
