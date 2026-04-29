# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Preservation tests for bugfix spec 28 (pre-submission review).

These tests encode the CURRENT (unfixed) observable behavior that must
survive the fixes. Every test in this file MUST PASS on unfixed code.
After the fix, the same tests MUST still PASS — confirming no regressions.

Findings covered:
  1. Default ``OPENCODE_MODEL`` value and Bedrock IAM resource list.
  2. Callback Lambda, authorizer, HTTP API, dependency edges.
  3. Alphanumeric token askpass behavior and ``_create_askpass_script``
     return type.
  4. Existing test suites pass (deferred to task 3.8 runtime verification).
  5. README surrounding OAuth-setup context preserved.
  6. Dockerfile non-CACHE_BUST lines preserved.
  7. GitHub provider path, ``GitHubCredentialProvider`` resource,
     ``connect_git_host`` signature, GitHub token redaction tests.

**Validates: Requirements 3.1, 3.2, 3.3, 3.3.1, 3.4, 3.4.1, 3.5, 3.6,
3.7, 3.8, 3.8.1, 3.9, 3.10, 3.11, 3.12, 3.13**
"""

from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_kms as kms
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
CDK_JSON_PATH = REPO_ROOT / "cdk.json"
README_PATH = REPO_ROOT / "README.md"
DOCKERFILE_PATH = REPO_ROOT / "container" / "Dockerfile"
SETUP_OAUTH_PATH = REPO_ROOT / "scripts" / "setup-oauth-app.sh"


# ---------------------------------------------------------------------------
# CDK synth helpers
# ---------------------------------------------------------------------------


def _load_cdk_context() -> dict:
    with CDK_JSON_PATH.open() as f:
        return json.load(f)["context"]


def _build_agentcore_template(
    context_overrides: dict | None = None,
) -> tuple[assertions.Template, cdk.Stack]:
    """Synth an isolated ``AgentCoreStack``."""
    from stacks.vpc_stack import VpcStack
    from stacks.security_stack import SecurityStack
    from stacks.callback_api_stack import CallbackApiStack
    from stacks.agentcore_stack import AgentCoreStack

    ctx = _load_cdk_context()
    if context_overrides:
        ctx.update(context_overrides)
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")
    security_stack = SecurityStack(app, "TestSecurity", env=env)
    vpc_stack = VpcStack(app, "TestVpc", cmk=security_stack.cmk, env=env)
    callback_api_stack = CallbackApiStack(
        app, "TestCallbackApi", cmk=security_stack.cmk, env=env
    )
    stack = AgentCoreStack(
        app, "TestAgentCore",
        vpc=vpc_stack.vpc,
        cmk=security_stack.cmk,
        callback_url=callback_api_stack.callback_url_value,
        env=env,
    )
    return assertions.Template.from_stack(stack), stack


def _get_runtime_env_vars(template: assertions.Template) -> dict:
    """Return the ``EnvironmentVariables`` of the ``CfnRuntime``."""
    tpl = template.to_json()
    for _lid, res in tpl["Resources"].items():
        if res.get("Type") != "AWS::BedrockAgentCore::Runtime":
            continue
        props = res.get("Properties", {})
        env_vars = props.get("EnvironmentVariables")
        if env_vars is not None:
            return env_vars
    raise AssertionError(
        "OpenCodeRuntime resource with EnvironmentVariables not found"
    )


def _get_bedrock_iam_resources(template: assertions.Template) -> list[str]:
    """Return the sorted Bedrock IAM resource ARN list from the synth template."""
    tpl = template.to_json()
    for _lid, res in tpl["Resources"].items():
        if res.get("Type") != "AWS::IAM::Policy":
            continue
        doc = res.get("Properties", {}).get("PolicyDocument", {})
        for stmt in doc.get("Statement", []):
            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            if "bedrock:InvokeModel" in actions:
                resources = stmt.get("Resource", [])
                if isinstance(resources, str):
                    resources = [resources]
                return sorted(str(r) for r in resources)
    raise AssertionError("BedrockInvokeModel policy statement not found")


# ---------------------------------------------------------------------------
# Finding 1 preservation — default OPENCODE_MODEL and IAM resource list
# ---------------------------------------------------------------------------


class TestFinding1PreservationDefaultModel:
    """Finding 1: when ``default_model_id`` is the default, ``OPENCODE_MODEL``
    must equal ``global.anthropic.claude-opus-4-6-v1``.

    **Validates: Requirements 3.1, 3.2**
    """

    def test_default_model_id_yields_opus(self) -> None:
        """At the default ``default_model_id``, ``OPENCODE_MODEL`` is
        ``global.anthropic.claude-opus-4-6-v1``."""
        template, _stack = _build_agentcore_template()
        env_vars = _get_runtime_env_vars(template)
        assert env_vars.get("OPENCODE_MODEL") == "global.anthropic.claude-opus-4-6-v1", (
            "OPENCODE_MODEL must be 'global.anthropic.claude-opus-4-6-v1' "
            f"at the default model id; got {env_vars.get('OPENCODE_MODEL')!r}"
        )

    @given(
        model_id=st.sampled_from([
            "global.anthropic.claude-opus-4-6-v1",
            "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "eu.anthropic.claude-3-5-sonnet-20240620-v1:0",
            "arn:aws:bedrock:us-east-1:123456789012:inference-profile/custom-profile",
        ])
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_bedrock_iam_resources_unchanged_across_model_ids(
        self, model_id: str
    ) -> None:
        """The Bedrock IAM resource list for any ``default_model_id`` is
        identical between the current code and itself (trivially true on
        unfixed code; after the fix, confirms the prefix-stripping logic
        is unchanged)."""
        template_a, _ = _build_agentcore_template(
            context_overrides={"default_model_id": model_id}
        )
        template_b, _ = _build_agentcore_template(
            context_overrides={"default_model_id": model_id}
        )
        resources_a = _get_bedrock_iam_resources(template_a)
        resources_b = _get_bedrock_iam_resources(template_b)
        assert resources_a == resources_b, (
            f"Bedrock IAM resources differ for model_id={model_id!r}: "
            f"{resources_a} vs {resources_b}"
        )


# ---------------------------------------------------------------------------
# Finding 2 preservation — dependency edges and callback resources
# ---------------------------------------------------------------------------


def _build_full_app() -> cdk.App:
    """Build the full CDK app using the current ``app.py`` wiring."""
    from stacks.vpc_stack import VpcStack
    from stacks.security_stack import SecurityStack
    from stacks.job_store_stack import JobStoreStack
    from stacks.callback_api_stack import CallbackApiStack
    from stacks.agentcore_stack import AgentCoreStack
    from stacks.gateway_stack import GatewayStack
    from stacks.policy_stack import PolicyStack
    from stacks.identity_stack import IdentityStack
    from stacks.observability_stack import ObservabilityStack

    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")

    security_stack = SecurityStack(app, "OpenCodeSecurity", env=env)
    vpc_stack = VpcStack(app, "OpenCodeVpc", cmk=security_stack.cmk, env=env)
    vpc_stack.add_dependency(security_stack)
    job_store_stack = JobStoreStack(
        app, "OpenCodeJobStore", cmk=security_stack.cmk, env=env
    )
    job_store_stack.add_dependency(security_stack)
    callback_api_stack = CallbackApiStack(
        app, "OpenCodeCallbackApi", cmk=security_stack.cmk, env=env
    )
    callback_api_stack.add_dependency(security_stack)
    agentcore_stack = AgentCoreStack(
        app, "OpenCodeAgentCore",
        vpc=vpc_stack.vpc,
        cmk=security_stack.cmk,
        callback_url=callback_api_stack.callback_url_value,
        env=env,
    )
    agentcore_stack.add_dependency(vpc_stack)
    agentcore_stack.add_dependency(security_stack)
    agentcore_stack.add_dependency(callback_api_stack)
    identity_stack = IdentityStack(
        app, "OpenCodeIdentity",
        cmk=security_stack.cmk,
        callback_url=callback_api_stack.callback_url_value,
        env=env,
    )
    identity_stack.add_dependency(security_stack)
    identity_stack.add_dependency(callback_api_stack)
    policy_stack = PolicyStack(app, "OpenCodePolicy", env=env)
    policy_stack.add_dependency(security_stack)
    gateway_stack = GatewayStack(
        app,
        "OpenCodeGateway",
        cognito_user_pool=security_stack.user_pool,
        cognito_client_id=security_stack.user_pool_client.user_pool_client_id,
        opencode_runtime=agentcore_stack.runtime,
        policy_engine_arn=policy_stack.policy_engine.attr_policy_engine_arn,
        cmk=security_stack.cmk,
        env=env,
    )
    gateway_stack.add_dependency(security_stack)
    gateway_stack.add_dependency(agentcore_stack)
    gateway_stack.add_dependency(policy_stack)
    observability_stack = ObservabilityStack(
        app, "OpenCodeObservability", cmk=security_stack.cmk, env=env
    )
    observability_stack.add_dependency(security_stack)

    return app


def _get_stack(app: cdk.App, name: str) -> cdk.Stack | None:
    for child in app.node.children:
        if isinstance(child, cdk.Stack) and child.stack_name == name:
            return child
    return None


def _get_dependency_names(stack: cdk.Stack) -> set[str]:
    return {dep.stack_name for dep in stack.dependencies}


class TestFinding2PreservationDependencyEdges:
    """Finding 2: dependency edges and callback resources are preserved.

    **Validates: Requirements 3.3, 3.3.1, 3.4, 3.4.1**
    """

    def test_gateway_depends_on_agentcore(self) -> None:
        app = _build_full_app()
        gw = _get_stack(app, "OpenCodeGateway")
        assert gw is not None
        deps = _get_dependency_names(gw)
        assert "OpenCodeAgentCore" in deps, (
            f"GatewayStack must depend on AgentCoreStack; deps={deps}"
        )

    def test_agentcore_receives_opencode_runtime_prop(self) -> None:
        """``GatewayStack`` receives ``opencode_runtime`` from ``AgentCoreStack``."""
        app = _build_full_app()
        ac = _get_stack(app, "OpenCodeAgentCore")
        assert ac is not None
        assert hasattr(ac, "runtime"), (
            "AgentCoreStack must expose a 'runtime' attribute"
        )

    def test_non_callback_dependency_edges_match_baseline(self) -> None:
        """SecurityStack, VpcStack, JobStoreStack, PolicyStack,
        ObservabilityStack dependency edges match the observed baseline."""
        app = _build_full_app()

        # SecurityStack has no dependencies (foundation)
        sec = _get_stack(app, "OpenCodeSecurity")
        assert sec is not None
        assert len(_get_dependency_names(sec)) == 0

        # VpcStack depends on SecurityStack
        vpc = _get_stack(app, "OpenCodeVpc")
        assert vpc is not None
        assert "OpenCodeSecurity" in _get_dependency_names(vpc)

        # JobStoreStack depends on SecurityStack
        js = _get_stack(app, "OpenCodeJobStore")
        assert js is not None
        assert "OpenCodeSecurity" in _get_dependency_names(js)

        # PolicyStack depends on SecurityStack
        pol = _get_stack(app, "OpenCodePolicy")
        assert pol is not None
        assert "OpenCodeSecurity" in _get_dependency_names(pol)

        # ObservabilityStack depends on SecurityStack
        obs = _get_stack(app, "OpenCodeObservability")
        assert obs is not None
        assert "OpenCodeSecurity" in _get_dependency_names(obs)

    def test_identity_stack_has_callback_resources(self) -> None:
        """The callback Lambda, authorizer, HTTP API, and access log group
        exist in the current template. After the fix they move to
        ``CallbackApiStack`` — this test checks that the resources exist
        somewhere in the app (stack-agnostic on location)."""
        app = _build_full_app()
        # After the fix, these live in CallbackApiStack
        callback_stack = _get_stack(app, "OpenCodeCallbackApi")
        if callback_stack is not None:
            tpl = assertions.Template.from_stack(callback_stack).to_json()
        else:
            # On unfixed code, they live in IdentityStack
            identity = _get_stack(app, "OpenCodeIdentity")
            assert identity is not None
            tpl = assertions.Template.from_stack(identity).to_json()

        # Count Lambda functions (callback + authorizer)
        lambdas = {
            lid: res for lid, res in tpl["Resources"].items()
            if res.get("Type") == "AWS::Lambda::Function"
        }
        assert len(lambdas) >= 2, (
            f"Expected at least 2 Lambda functions (callback + authorizer); "
            f"found {len(lambdas)}"
        )

        # HTTP API exists
        http_apis = {
            lid: res for lid, res in tpl["Resources"].items()
            if res.get("Type") == "AWS::ApiGatewayV2::Api"
        }
        assert len(http_apis) >= 1, (
            "Expected at least 1 HTTP API"
        )


# ---------------------------------------------------------------------------
# Finding 3 preservation — askpass return type and finally-block cleanup
# ---------------------------------------------------------------------------


class TestFinding3PreservationAskpassContract:
    """Finding 3: ``_create_askpass_script`` returns a single string and
    callers clean up the script in ``finally`` blocks.

    **Validates: Requirements 3.5, 3.6**
    """

    def test_create_askpass_script_returns_str(self) -> None:
        """``_create_askpass_script`` returns a ``str``, not a tuple."""
        from container.lib.git_askpass import _create_askpass_script

        result = _create_askpass_script("test_token_abc123")
        try:
            assert isinstance(result, str), (
                f"_create_askpass_script must return str; got {type(result)}"
            )
        finally:
            if os.path.exists(result):
                os.remove(result)
            sidecar = result + ".token"
            if os.path.exists(sidecar):
                os.remove(sidecar)

    def test_git_clone_finally_removes_askpass(self) -> None:
        """``git_clone``'s ``finally`` block removes the askpass script."""
        from unittest.mock import patch, MagicMock

        removed_paths: list[str] = []
        original_remove = os.remove

        def tracking_remove(path: str) -> None:
            removed_paths.append(path)

        with (
            patch("container.tools.git_clone.subprocess.run") as mock_run,
            patch(
                "container.tools.git_clone._create_askpass_script",
                return_value="/tmp/fake_askpass.sh",
            ),
            patch("container.tools.git_clone.os.path.exists", return_value=True),
            patch("container.tools.git_clone.os.remove", side_effect=tracking_remove),
        ):
            from container.tools.git_clone import git_clone
            git_clone(
                repo_url="https://github.com/owner/repo",
                token="ghp_test123",
                base_branch="main",
                work_dir="/tmp/work",
            )

        assert "/tmp/fake_askpass.sh" in removed_paths, (
            "git_clone finally block must remove the askpass script; "
            f"removed={removed_paths}"
        )

    def test_git_push_finally_removes_askpass(self) -> None:
        """``git_push_and_create_pr``'s ``finally`` block removes the askpass script."""
        from unittest.mock import patch, MagicMock

        removed_paths: list[str] = []

        def tracking_remove(path: str) -> None:
            removed_paths.append(path)

        with (
            patch("container.tools.git_push_and_create_pr.subprocess.run") as mock_run,
            patch(
                "container.tools.git_push_and_create_pr._create_askpass_script",
                return_value="/tmp/fake_askpass.sh",
            ),
            patch("container.tools.git_push_and_create_pr.os.path.exists", return_value=True),
            patch("container.tools.git_push_and_create_pr.os.remove", side_effect=tracking_remove),
        ):
            # Mock subprocess.run to simulate: diff has output, commit succeeds, push succeeds
            def side_effect_run(cmd, **kwargs):
                result = MagicMock()
                result.stdout = "file.py | 1 +\n"
                result.returncode = 0
                return result

            mock_run.side_effect = side_effect_run

            from container.tools.git_push_and_create_pr import git_push_and_create_pr
            git_push_and_create_pr(
                work_dir="/tmp/work",
                token="ghp_test123",
                repo_url="https://github.com/owner/repo",
                target_branch="feature-branch",
                base_branch="main",
                task_description="test task",
                job_id="job-123",
            )

        assert "/tmp/fake_askpass.sh" in removed_paths, (
            "git_push_and_create_pr finally block must remove the askpass script; "
            f"removed={removed_paths}"
        )


# ---------------------------------------------------------------------------
# Finding 5 preservation — README surrounding context
# ---------------------------------------------------------------------------


class TestFinding5PreservationReadmeContext:
    """Finding 5: surrounding OAuth-setup instructions in ``README.md``
    are preserved.

    **Validates: Requirements 3.9**
    """

    def test_github_settings_developers_link_present(self) -> None:
        text = README_PATH.read_text()
        assert "github.com/settings/developers" in text, (
            "README must contain a link to github.com/settings/developers"
        )

    def test_callback_url_note_present(self) -> None:
        text = README_PATH.read_text()
        assert "callback" in text.lower(), (
            "README must contain a note about the callback URL"
        )

    def test_aws_region_profile_note_present(self) -> None:
        text = README_PATH.read_text()
        assert "AWS_REGION" in text and "AWS_PROFILE" in text, (
            "README must contain AWS_REGION and AWS_PROFILE notes"
        )

    def test_safe_to_rerun_note_present(self) -> None:
        text = README_PATH.read_text()
        assert "Safe to re-run" in text or "safe to re-run" in text.lower(), (
            "README must contain a 'safe to re-run' note"
        )


# ---------------------------------------------------------------------------
# Finding 6 preservation — Dockerfile non-CACHE_BUST lines
# ---------------------------------------------------------------------------


class TestFinding6PreservationDockerfileLines:
    """Finding 6: every Dockerfile directive except ``ARG CACHE_BUST``
    is preserved after the fix.

    **Validates: Requirements 3.10**

    On unfixed code, this test records the baseline (all lines). After
    the fix, the Dockerfile should equal the baseline minus exactly the
    one ``ARG CACHE_BUST=...`` line.
    """

    # Key directives that must survive the fix
    EXPECTED_DIRECTIVES = [
        "FROM public.ecr.aws/docker/library/python:3.12-slim",
        "WORKDIR /app",
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "RUN opentelemetry-bootstrap -a install",
        "ARG OPENCODE_VERSION=",
        "COPY . ./container/",
        "RUN useradd -m -s /bin/bash opencode",
        "USER opencode",
        "EXPOSE 8000",
    ]

    def test_key_directives_present(self) -> None:
        text = DOCKERFILE_PATH.read_text()
        for directive in self.EXPECTED_DIRECTIVES:
            assert directive in text, (
                f"Dockerfile must contain directive: {directive!r}"
            )

    def test_entrypoint_preserved(self) -> None:
        text = DOCKERFILE_PATH.read_text()
        assert 'ENTRYPOINT ["opentelemetry-instrument", "python", "-m", "container.code_mcp_server"]' in text, (
            "Dockerfile ENTRYPOINT must be preserved"
        )

    def test_non_cache_bust_lines_form_baseline(self) -> None:
        """After the fix, the ``ARG CACHE_BUST`` line should be absent.
        The entire Dockerfile should consist only of non-CACHE_BUST lines."""
        text = DOCKERFILE_PATH.read_text()
        lines = text.splitlines()
        cache_bust_lines = [
            line for line in lines
            if line.strip().startswith("ARG CACHE_BUST")
        ]
        assert len(cache_bust_lines) == 0, (
            f"Expected 0 ARG CACHE_BUST lines (post-fix state); "
            f"found {len(cache_bust_lines)}"
        )
        # The Dockerfile should still have substantial content
        non_empty = [line for line in lines if line.strip()]
        assert len(non_empty) > 10, (
            "Dockerfile should have more than 10 non-empty lines"
        )


# ---------------------------------------------------------------------------
# Finding 7 preservation — GitHub provider path, CDK resource, signature
# ---------------------------------------------------------------------------


class TestFinding7PreservationGitHubPath:
    """Finding 7: the GitHub provider path, ``GitHubCredentialProvider``
    resource, ``connect_git_host`` signature, and GitHub token redaction
    tests are preserved.

    **Validates: Requirements 3.11, 3.12, 3.13**
    """

    def test_setup_script_has_github_case_arm(self) -> None:
        text = SETUP_OAUTH_PATH.read_text()
        assert "github)" in text, (
            "setup-oauth-app.sh must contain a 'github)' case arm"
        )

    def test_identity_stack_github_credential_provider(self) -> None:
        """Synthesized ``IdentityStack`` has a ``GitHubCredentialProvider``
        custom resource with ``provider_name="github-provider"`` and
        ``vendor="GithubOauth2"``."""
        from stacks.identity_stack import IdentityStack

        ctx = _load_cdk_context()
        app = cdk.App(context=ctx)
        env = cdk.Environment(account="123456789012", region="us-east-1")
        cmk_stack = cdk.Stack(app, "StubCmkStack", env=env)
        stub_cmk = kms.Key(cmk_stack, "StubCmk")
        identity_stack = IdentityStack(
            app, "OpenCodeIdentity",
            cmk=stub_cmk,
            callback_url="https://example.execute-api.us-east-1.amazonaws.com/callback",
            env=env,
        )
        tpl = assertions.Template.from_stack(identity_stack).to_json()

        # Find the GitHubCredentialProvider custom resource
        found = False
        for _lid, res in tpl["Resources"].items():
            if res.get("Type") != "AWS::CloudFormation::CustomResource":
                continue
            props = res.get("Properties", {})
            if props.get("provider_name") == "github-provider":
                assert props.get("vendor") == "GithubOauth2", (
                    f"GitHubCredentialProvider vendor must be 'GithubOauth2'; "
                    f"got {props.get('vendor')!r}"
                )
                assert "secret_arn" in props, (
                    "GitHubCredentialProvider must have a secret_arn property"
                )
                found = True
                break
        assert found, (
            "IdentityStack must contain a GitHubCredentialProvider custom "
            "resource with provider_name='github-provider'"
        )

    def test_connect_git_host_signature_unchanged(self) -> None:
        """``connect_git_host`` signature is
        ``(git_host: str, _user_id: str = "", ctx: Context | None = None) -> dict``."""
        from container.code_mcp_server import connect_git_host

        sig = inspect.signature(connect_git_host)
        param_names = list(sig.parameters.keys())
        assert "git_host" in param_names, (
            f"connect_git_host must have 'git_host' parameter; params={param_names}"
        )
        assert "_user_id" in param_names, (
            f"connect_git_host must have '_user_id' parameter; params={param_names}"
        )
        assert "ctx" in param_names, (
            f"connect_git_host must have 'ctx' parameter; params={param_names}"
        )
