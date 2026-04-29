# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Bug-condition exploration tests for bugfix spec 28 (pre-submission review).

These tests encode the expected (post-fix) behavior described by
``design.md`` Properties 1-6 and Property 12. Running them against the
UNFIXED tree MUST produce at least one failure per finding; each failure
is the counterexample that confirms the bug exists.

Findings exercised (matching ``tasks.md`` task 1):

  1. Hardcoded ``OPENCODE_MODEL`` in ``stacks/agentcore_stack.py``.
  2. Hardcoded ``oauth_callback_url`` context + absence of
     ``CallbackApiStack``.
  3. Shell-quoting defect in ``container/lib/git_askpass.py``.
  4. Unpinned dependencies + vestigial Strands decorator usage.
  5. Duplicated OAuth setup command in ``README.md``.
  6. Dead ``ARG CACHE_BUST`` in ``container/Dockerfile``.
  7. Untested GHE/GitLab paths documented + implemented as first-class.

These tests intentionally do NOT try to "fix" anything when they fail —
failure is the signal that the bug is present. They will be re-run
post-fix (task 3.7) to confirm every finding has been resolved.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Iterator

import aws_cdk as cdk
from aws_cdk import assertions
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
CDK_JSON_PATH = REPO_ROOT / "cdk.json"
REQUIREMENTS_PATH = REPO_ROOT / "container" / "requirements.txt"
DOCKERFILE_PATH = REPO_ROOT / "container" / "Dockerfile"
README_PATH = REPO_ROOT / "README.md"
ARCHITECTURE_PATH = REPO_ROOT / "docs" / "ARCHITECTURE.md"
TOOLS_PATH = REPO_ROOT / "docs" / "TOOLS.md"
MCP_SERVER_PATH = REPO_ROOT / "container" / "code_mcp_server.py"
SETUP_OAUTH_PATH = REPO_ROOT / "scripts" / "setup-oauth-app.sh"
TOOLS_DIR = REPO_ROOT / "container" / "tools"
TOOL_FILES = [
    TOOLS_DIR / "resolve_git_credential.py",
    TOOLS_DIR / "git_push_and_create_pr.py",
    TOOLS_DIR / "git_clone.py",
    TOOLS_DIR / "scan_and_strip_credentials.py",
    TOOLS_DIR / "run_opencode_acp.py",
    TOOLS_DIR / "__init__.py",
]
CREDENTIAL_SCANNER_TEST = (
    REPO_ROOT / "tests" / "property" / "test_credential_scanner_property.py"
)
GIT_CLONE_ASKPASS_TEST = (
    REPO_ROOT / "tests" / "property" / "test_git_clone_askpass.py"
)


# ---------------------------------------------------------------------------
# CDK synth helpers (Findings 1 & 2)
# ---------------------------------------------------------------------------


def _load_cdk_context() -> dict:
    with CDK_JSON_PATH.open() as f:
        return json.load(f)["context"]


def _build_agentcore_template(
    context_overrides: dict | None = None,
) -> tuple[assertions.Template, cdk.Stack]:
    """Synth an isolated ``AgentCoreStack`` for Finding 1 assertions.

    Uses the same helper shape as ``tests/unit/test_agentcore_stack.py`` so
    context handling and stack wiring stay consistent across the suite.
    """
    from stacks.vpc_stack import VpcStack
    from stacks.security_stack import SecurityStack
    from stacks.agentcore_stack import AgentCoreStack

    ctx = _load_cdk_context()
    if context_overrides:
        ctx.update(context_overrides)
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")
    security_stack = SecurityStack(app, "TestSecurity", env=env)
    vpc_stack = VpcStack(app, "TestVpc", cmk=security_stack.cmk, env=env)

    # CallbackApiStack provides the callback_url for AgentCoreStack
    from stacks.callback_api_stack import CallbackApiStack
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
    """Return the ``EnvironmentVariables`` property of ``OpenCodeRuntime``.

    The synthesized runtime is a ``AWS::BedrockAgentCore::Runtime`` resource
    that this stack explicitly names ``OpenCodeRuntime`` (CDK suffixes it
    with a hash). Look up the resource by type + ``EnvironmentVariables``
    presence.
    """
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


# ---------------------------------------------------------------------------
# Finding 1 — ``OPENCODE_MODEL`` must equal the resolved ``default_model_id``
# ---------------------------------------------------------------------------


# Matches tasks.md task 1 bullet: Hypothesis ``st.sampled_from`` over three
# non-default model ids (us.*, eu.*, and a full inference-profile ARN).
_NON_DEFAULT_MODEL_IDS = st.sampled_from(
    [
        "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "eu.anthropic.claude-3-5-sonnet-20240620-v1:0",
        (
            "arn:aws:bedrock:us-east-1:123456789012:"
            "inference-profile/custom-profile"
        ),
    ]
)


class TestFinding1OpencodeModelTracksContext:
    """Finding 1: ``OPENCODE_MODEL`` must track the context ``default_model_id``.

    **Validates: Requirements 1.1, 2.1**

    Bug condition (from ``design.md`` Finding 1):
        ``default_model_id != "global.anthropic.claude-opus-4-6-v1"``.

    On unfixed code, ``OPENCODE_MODEL`` is the hardcoded string
    ``"global.anthropic.claude-opus-4-6-v1"`` regardless of the context
    value — this assertion therefore FAILS on unfixed code.
    """

    @given(model_id=_NON_DEFAULT_MODEL_IDS)
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_opencode_model_equals_default_model_id(self, model_id: str) -> None:
        template, _stack = _build_agentcore_template(
            context_overrides={"default_model_id": model_id}
        )
        env_vars = _get_runtime_env_vars(template)
        assert env_vars.get("OPENCODE_MODEL") == model_id, (
            "OPENCODE_MODEL must equal the resolved default_model_id "
            f"(context={model_id!r}, got={env_vars.get('OPENCODE_MODEL')!r})"
        )


# ---------------------------------------------------------------------------
# Finding 2 — ``OAUTH_CALLBACK_URL`` must come from ``CallbackApiStack``
# ---------------------------------------------------------------------------


def _build_full_app_without_oauth_context() -> cdk.App:
    """Replicate ``app.py`` wiring with the ``oauth_callback_url`` removed.

    This mirrors the "fresh clone, no operator override" bug condition from
    ``design.md`` Finding 2 — the current repo ships a stale
    ``iregt9k730`` URL in ``cdk.json`` that the runtime reads verbatim.
    """
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
    # Simulate "no override" by clearing the stale default.
    ctx.pop("oauth_callback_url", None)

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
        app,
        "OpenCodeAgentCore",
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


def _find_callback_api_stack(app: cdk.App) -> cdk.Stack | None:
    for child in app.node.children:
        if isinstance(child, cdk.Stack) and "CallbackApi" in child.stack_name:
            return child
    return None


class TestFinding2OAuthCallbackComesFromCallbackApiStack:
    """Finding 2: ``OAUTH_CALLBACK_URL`` must be a cross-stack import
    from a ``CallbackApiStack``.

    **Validates: Requirements 1.2, 2.2**

    Bug condition (from ``design.md`` Finding 2):
        ``oauth_callback_url`` context is absent OR equals the stale
        ``iregt9k730`` URL.

    On unfixed code, the env var is a literal string and
    ``CallbackApiStack`` does not exist — both assertions FAIL.
    """

    def test_callback_api_stack_exists(self) -> None:
        app = _build_full_app_without_oauth_context()
        stack = _find_callback_api_stack(app)
        assert stack is not None, (
            "CallbackApiStack must be present in the app (expected stack name "
            "like 'OpenCodeCallbackApi'). On unfixed code there is no such "
            "stack — the callback HTTP API still lives inside "
            "OpenCodeIdentity."
        )

    def test_oauth_callback_url_is_fn_import_value(self) -> None:
        app = _build_full_app_without_oauth_context()
        # Find AgentCoreStack
        agent_stack = None
        for child in app.node.children:
            if (
                isinstance(child, cdk.Stack)
                and child.stack_name == "OpenCodeAgentCore"
            ):
                agent_stack = child
                break
        assert agent_stack is not None, "OpenCodeAgentCore stack not found"

        template = assertions.Template.from_stack(agent_stack)
        env_vars = _get_runtime_env_vars(template)
        callback = env_vars.get("OAUTH_CALLBACK_URL")

        # Must be a CloudFormation intrinsic (dict with Fn::ImportValue),
        # NOT a literal string and NOT an empty string.
        assert isinstance(callback, dict), (
            "OAUTH_CALLBACK_URL must be a CloudFormation intrinsic "
            "({'Fn::ImportValue': ...}) referencing CallbackApiStack's "
            f"OAuthCallbackUrl output; got literal: {callback!r}"
        )
        # The callback URL is constructed as f"{http_api.url}callback" which
        # CDK resolves to a Fn::Join containing an Fn::ImportValue of the
        # API Gateway ID. Check that Fn::ImportValue appears somewhere in
        # the rendered structure (it may be nested inside Fn::Join).
        rendered = json.dumps(callback)
        assert "Fn::ImportValue" in rendered, (
            "OAUTH_CALLBACK_URL intrinsic must contain Fn::ImportValue; got "
            f"{callback!r}"
        )
        assert "Callback" in rendered or "OAuthCallback" in rendered, (
            "Fn::ImportValue must reference the CallbackApiStack "
            f"OAuthCallbackUrl export; got {callback!r}"
        )

    def test_cdk_synth_has_no_dependency_cycle(self) -> None:
        """The synthesized app MUST produce a cycle-free dependency graph.

        We rely on ``app.synth()`` itself to raise on cycles — a successful
        call produces a cloud assembly with every stack template. On
        unfixed code, adding a ``CallbackApiStack`` that both
        ``AgentCoreStack`` and ``IdentityStack`` depend on would clash with
        the existing ``IdentityStack -> AgentCoreStack`` edge, so the
        assertion here is simply "synth succeeds and CallbackApiStack is
        present" (the stack-presence check above already covers the "no
        CallbackApiStack" failure mode on unfixed code).
        """
        app = _build_full_app_without_oauth_context()
        assembly = app.synth()
        stack_names = [s.stack_name for s in assembly.stacks]
        assert any("Callback" in n for n in stack_names), (
            "Synthesized cloud assembly must contain a CallbackApiStack; "
            f"got: {stack_names!r}"
        )


# ---------------------------------------------------------------------------
# Finding 3 — Shell-quoting defect in ``git_askpass.py``
# ---------------------------------------------------------------------------


def _run_askpass_for_token(token: str) -> subprocess.CompletedProcess:
    """Create the askpass script, run it with bash, then clean up.

    Returns the completed subprocess so callers can inspect stdout /
    returncode. Removes both the script and any sidecar file regardless
    of test outcome.
    """
    # Import lazily so conftest's ``strands`` stub is in place before any
    # ``container.tools`` module imports Strands.
    from container.lib.git_askpass import _create_askpass_script

    script_path = _create_askpass_script(token)
    sidecar = script_path + ".token"
    try:
        return subprocess.run(
            ["bash", script_path],
            capture_output=True,
            timeout=10,
        )
    finally:
        for p in (script_path, sidecar):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


# Quoting-counterexample tokens called out by tasks.md. Kept here as a
# documentation/reference list; the individual test methods below exercise
# each shape with a dedicated assertion and error message.
_DETERMINISTIC_BUG_TOKENS = [
    "ab'cd",     # embedded single quote breaks single-quoted literal
    "-nfoo",     # ``echo -n`` flag: suppresses trailing newline
    "-efoo\\n",  # ``echo -e`` flag: enables backslash escapes
    "-Ebar",     # ``echo -E`` flag: disables backslash escapes
]


class TestFinding3AskpassPrintsTokenByteForByte:
    """Finding 3: ``bash <askpass>`` must print the token followed by a
    single newline for ALL byte sequences, including single-quote and
    ``echo``-flag counterexamples.

    **Validates: Requirements 1.3, 1.4, 2.3, 2.4**

    Bug condition (from ``design.md`` Finding 3):
        token contains ``'`` OR starts with ``-n`` / ``-e`` / ``-E``.

    On unfixed code, ``_create_askpass_script`` writes
    ``#!/bin/sh\\necho '<token>'\\n`` — for ``ab'cd`` the embedded quote
    closes the literal and bash errors; for ``-nfoo`` ``echo`` treats
    the token as a flag and suppresses the newline. Either failure
    confirms the bug.

    .. note::
       The echo-flag counterexamples (``-n``, ``-e``, ``-E``) only manifest
       when the script is dispatched through a shell whose ``echo`` built-in
       honours those flags. POSIX ``sh`` (dash, legacy ``bash --posix``)
       does; ``bash`` out-of-the-box does not. Git invokes ``GIT_ASKPASS``
       via ``/bin/sh`` (honours ``-e``), so the bug is real in production
       even though the ``bash <script>`` invocation below may not expose it
       on every platform. The ``ab'`` single-quote counterexample is
       shell-independent and is what the Hypothesis strategy reliably
       surfaces.
    """

    def test_embedded_single_quote(self) -> None:
        token = "ab'cd"
        result = _run_askpass_for_token(token)
        assert result.returncode == 0, (
            f"bash askpass must exit 0 for token {token!r}; "
            f"stderr={result.stderr!r}, returncode={result.returncode}"
        )
        assert result.stdout == token.encode("utf-8") + b"\n", (
            f"bash askpass must print token+newline for {token!r}; "
            f"stdout={result.stdout!r}"
        )

    def test_echo_n_flag_prefix(self) -> None:
        token = "-nfoo"
        result = _run_askpass_for_token(token)
        assert result.returncode == 0
        assert result.stdout == token.encode("utf-8") + b"\n", (
            f"bash askpass must print the literal token (including "
            f"leading -n) followed by a newline for {token!r}; "
            f"stdout={result.stdout!r}"
        )

    def test_echo_e_flag_prefix_with_backslash(self) -> None:
        # Literal two-character sequence: backslash + letter n.
        token = "-efoo\\n"
        result = _run_askpass_for_token(token)
        assert result.returncode == 0
        assert result.stdout == token.encode("utf-8") + b"\n", (
            f"bash askpass must print the literal token (no backslash "
            f"expansion) followed by a newline for {token!r}; "
            f"stdout={result.stdout!r}"
        )

    def test_echo_E_flag_prefix(self) -> None:
        token = "-Ebar"
        result = _run_askpass_for_token(token)
        assert result.returncode == 0
        assert result.stdout == token.encode("utf-8") + b"\n", (
            f"bash askpass must print the literal token (including "
            f"leading -E) followed by a newline for {token!r}; "
            f"stdout={result.stdout!r}"
        )

    # Scoped Hypothesis strategy over the four counterexample shapes.
    # We restrict to printable ASCII (no NUL, no newlines) so the
    # byte-for-byte comparison is meaningful without platform-dependent
    # shell behavior on newline-containing input.
    _printable = st.text(
        alphabet=st.characters(
            min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="\n\r"
        ),
        min_size=0,
        max_size=32,
    )
    _scoped_tokens = st.one_of(
        _printable.map(lambda s: "ab'" + s),
        _printable.map(lambda s: "-n" + s),
        _printable.map(lambda s: "-e" + s),
        _printable.map(lambda s: "-E" + s),
    ).filter(lambda s: len(s) > 0)

    @given(token=_scoped_tokens)
    @settings(
        max_examples=25,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_scoped_counterexample_strategy(self, token: str) -> None:
        """For every token matching the bug condition, the script must
        produce exactly ``token + "\\n"`` on stdout with exit 0."""
        result = _run_askpass_for_token(token)
        assert result.returncode == 0, (
            f"bash askpass must exit 0 for token {token!r}; "
            f"stderr={result.stderr!r}"
        )
        assert result.stdout == token.encode("utf-8") + b"\n", (
            f"bash askpass must print token+newline for {token!r}; "
            f"stdout={result.stdout!r}"
        )


# ---------------------------------------------------------------------------
# Finding 4 — Pinned deps + no Strands dependency / decorators
# ---------------------------------------------------------------------------


_PIN_RE = re.compile(r"^[A-Za-z0-9_.\-]+==[A-Za-z0-9_.+\-]+$")
_STRANDS_AGENTS_RE = re.compile(r"^strands-agents(\[.*\])?(==|>=|<=|~=|!=)")
_STRANDS_TOOLS_RE = re.compile(r"^strands-agents-tools(==|>=|<=|~=|!=)")
_AT_TOOL_DECORATOR_RE = re.compile(r"^@tool\b", re.MULTILINE)


def _iter_requirement_lines(text: str) -> Iterator[str]:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        yield line


class TestFinding4PinnedDepsAndNoStrands:
    """Finding 4: every dependency pinned with ``==``, no Strands deps, no
    ``@tool`` decorator usage anywhere in ``container/tools/*.py``.

    **Validates: Requirements 1.5, 1.5.1, 2.5, 2.5.1**

    Bug conditions (from ``design.md`` Finding 4):
      * any non-comment line in ``requirements.txt`` uses ``>=``
      * any line matches ``^strands-agents(\\[.*\\])?`` or
        ``^strands-agents-tools``
      * any ``container/tools/*.py`` contains ``from strands import`` or
        a ``@tool`` decorator.
    """

    def test_requirements_all_pinned_with_double_equals(self) -> None:
        text = REQUIREMENTS_PATH.read_text()
        offenders = [
            line
            for line in _iter_requirement_lines(text)
            if not _PIN_RE.match(line)
        ]
        assert not offenders, (
            "Every non-comment, non-blank line in container/requirements.txt "
            "must match ^[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+$; offenders="
            f"{offenders!r}"
        )

    def test_requirements_has_no_strands_agents(self) -> None:
        text = REQUIREMENTS_PATH.read_text()
        offenders = [
            line
            for line in _iter_requirement_lines(text)
            if _STRANDS_AGENTS_RE.match(line)
        ]
        assert not offenders, (
            "container/requirements.txt must not depend on strands-agents; "
            f"offenders={offenders!r}"
        )

    def test_requirements_has_no_strands_agents_tools(self) -> None:
        text = REQUIREMENTS_PATH.read_text()
        offenders = [
            line
            for line in _iter_requirement_lines(text)
            if _STRANDS_TOOLS_RE.match(line)
        ]
        assert not offenders, (
            "container/requirements.txt must not depend on "
            f"strands-agents-tools; offenders={offenders!r}"
        )

    def test_tool_files_have_no_strands_import(self) -> None:
        offenders: list[tuple[str, str]] = []
        for path in TOOL_FILES:
            text = path.read_text()
            if "from strands import" in text:
                offenders.append((str(path.relative_to(REPO_ROOT)), text.splitlines()[0]))
        assert not offenders, (
            "Container tool files must not import from strands; offenders="
            f"{offenders!r}"
        )

    def test_tool_files_have_no_at_tool_decorator(self) -> None:
        offenders: list[tuple[str, str]] = []
        for path in TOOL_FILES:
            text = path.read_text()
            matches = _AT_TOOL_DECORATOR_RE.findall(text)
            if matches:
                offenders.append((str(path.relative_to(REPO_ROOT)), matches))
        assert not offenders, (
            "Container tool files must not use the @tool decorator; "
            f"offenders={offenders!r}"
        )

    def test_tools_init_docstring_drops_strands(self) -> None:
        text = (TOOLS_DIR / "__init__.py").read_text()
        # Extract module docstring (triple-quoted string at top of file).
        m = re.search(
            r'^\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')',
            text,
            re.DOTALL | re.MULTILINE,
        )
        assert m is not None, (
            "container/tools/__init__.py must have a module docstring"
        )
        docstring = m.group(1)
        assert "Strands" not in docstring, (
            "container/tools/__init__.py module docstring must not "
            f"reference Strands; got: {docstring!r}"
        )


# ---------------------------------------------------------------------------
# Finding 5 — README command must not be concatenated
# ---------------------------------------------------------------------------


class TestFinding5ReadmeCommandNotConcatenated:
    """Finding 5: ``README.md`` must not contain the broken
    ``setup-oauth-app.sh./scripts/setup-oauth-app.sh`` string and must
    contain the correct ``./scripts/setup-oauth-app.sh`` as a standalone
    line.

    **Validates: Requirements 1.6, 2.6**
    """

    def test_no_concatenated_command(self) -> None:
        text = README_PATH.read_text()
        assert "setup-oauth-app.sh./scripts/setup-oauth-app.sh" not in text, (
            "README.md must not contain the concatenated broken command"
        )

    def test_correct_command_line_present(self) -> None:
        text = README_PATH.read_text()
        lines = [line.strip() for line in text.splitlines()]
        assert "./scripts/setup-oauth-app.sh" in lines, (
            "README.md must contain a standalone './scripts/setup-oauth-app.sh' "
            "line inside the OAuth setup code block"
        )


# ---------------------------------------------------------------------------
# Finding 6 — Dockerfile must not contain ``CACHE_BUST``
# ---------------------------------------------------------------------------


class TestFinding6DockerfileNoCacheBust:
    """Finding 6: ``container/Dockerfile`` must not mention ``CACHE_BUST``
    anywhere (ARG line or RUN reference).

    **Validates: Requirements 1.7, 2.7**
    """

    def test_cache_bust_absent(self) -> None:
        text = DOCKERFILE_PATH.read_text()
        assert "CACHE_BUST" not in text, (
            "container/Dockerfile must not contain CACHE_BUST; found in file"
        )


# ---------------------------------------------------------------------------
# Finding 7 — No GHE / GitLab references in docs, source, or tests
# ---------------------------------------------------------------------------


_GHE_GITLAB_PHRASES = ("GitHub Enterprise", "GHE", "GitLab")


class TestFinding7NoGheOrGitlabReferences:
    """Finding 7: remove every reference to ``GitHub Enterprise`` / ``GHE``
    / ``GitLab`` from docs, source, scripts, and the credential-scanner
    property test; reject ``--provider ghe`` / ``--provider gitlab`` at the
    CLI.

    **Validates: Requirements 1.8, 1.9, 2.8, 2.9**
    """

    DOC_AND_SOURCE_FILES = [
        README_PATH,
        ARCHITECTURE_PATH,
        TOOLS_PATH,
        MCP_SERVER_PATH,
        SETUP_OAUTH_PATH,
    ]

    def test_no_ghe_or_gitlab_phrases_in_docs_and_source(self) -> None:
        offenders: list[tuple[str, str, str]] = []
        for path in self.DOC_AND_SOURCE_FILES:
            text = path.read_text()
            for phrase in _GHE_GITLAB_PHRASES:
                # Case-sensitive — "GHE" should not match "github" etc.
                if phrase in text:
                    rel = str(path.relative_to(REPO_ROOT))
                    offenders.append((rel, phrase, "present"))
        assert not offenders, (
            "GHE/GitLab references must be absent from docs and source; "
            f"offenders={offenders!r}"
        )

    def test_setup_script_has_no_ghe_case_arm(self) -> None:
        text = SETUP_OAUTH_PATH.read_text()
        assert "ghe)" not in text, (
            "scripts/setup-oauth-app.sh must not contain a 'ghe)' case arm"
        )

    def test_setup_script_has_no_gitlab_case_arm(self) -> None:
        text = SETUP_OAUTH_PATH.read_text()
        assert "gitlab)" not in text, (
            "scripts/setup-oauth-app.sh must not contain a 'gitlab)' case arm"
        )

    def test_credential_scanner_test_has_no_gitlab_pat_strategy(self) -> None:
        text = CREDENTIAL_SCANNER_TEST.read_text()
        assert "_gitlab_pat" not in text, (
            "tests/property/test_credential_scanner_property.py must not "
            "define a _gitlab_pat strategy"
        )

    def test_credential_scanner_test_has_no_gitlab_pat_redacted_test(self) -> None:
        text = CREDENTIAL_SCANNER_TEST.read_text()
        assert "test_gitlab_pat_redacted" not in text, (
            "tests/property/test_credential_scanner_property.py must not "
            "define test_gitlab_pat_redacted"
        )

    def test_git_clone_askpass_host_strategy_excludes_gitlab(self) -> None:
        text = GIT_CLONE_ASKPASS_TEST.read_text()
        # The ``_git_host`` strategy is defined via ``st.sampled_from([...])``.
        # We only require that ``"gitlab.com"`` is not in the file body.
        assert "gitlab.com" not in text, (
            "tests/property/test_git_clone_askpass.py _git_host strategy "
            "must not include 'gitlab.com'"
        )

    def test_setup_script_rejects_ghe_provider(self) -> None:
        """``./scripts/setup-oauth-app.sh --provider ghe --help`` must exit
        non-zero after the fix. On unfixed code, ``--help`` short-circuits
        before ``--provider`` is validated and the script exits 0 —
        confirming the bug.
        """
        result = subprocess.run(
            [
                "bash",
                str(SETUP_OAUTH_PATH),
                "--provider",
                "ghe",
                "--help",
            ],
            capture_output=True,
            timeout=10,
            env={**os.environ, "AWS_REGION": "us-east-1"},
        )
        assert result.returncode != 0, (
            "setup-oauth-app.sh must reject --provider ghe (exit non-zero); "
            f"got exit={result.returncode}, stdout={result.stdout!r}"
        )

    def test_setup_script_rejects_gitlab_provider(self) -> None:
        result = subprocess.run(
            [
                "bash",
                str(SETUP_OAUTH_PATH),
                "--provider",
                "gitlab",
                "--help",
            ],
            capture_output=True,
            timeout=10,
            env={**os.environ, "AWS_REGION": "us-east-1"},
        )
        assert result.returncode != 0, (
            "setup-oauth-app.sh must reject --provider gitlab (exit non-zero); "
            f"got exit={result.returncode}, stdout={result.stdout!r}"
        )
