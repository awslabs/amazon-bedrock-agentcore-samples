# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Preservation tests for spec 30-elicitation-error-handling.

These tests encode the *observed* (pre-fix) behavior that must survive
the fix for spec 30. They form the baseline that Property 2 (preservation)
from ``design.md`` must preserve byte-for-byte once the fix lands.

Per ``tasks.md`` task 2, five preservation sub-cases are covered:

  1. **Preservation 1** - Successful ``code`` pipeline produces
     ``status == "complete"`` with mirrored ``pr_url`` / ``stop_reason`` /
     ``files_edited`` fields (clause 3.1).
  2. **Preservation 2** - ``_elicit_with_timeout`` returns ``None`` on
     ``asyncio.TimeoutError`` (clause 3.7).
  3. **Preservation 3** - ``_on_oauth_needed`` returns ``False`` when
     ``ctx.elicit`` returns ``result.action == "cancel"``; the pipeline
     surfaces ``error == "OAuth authorization cancelled"`` (clause 3.4).
  4. **Preservation 4** - ``connect_git_host`` with a stubbed
     ``_elicit_with_timeout`` returning ``None`` produces a structured
     ``{"status": "action_required", "authorization_url": "<url>"}``
     response (clauses 3.6, 3.8).
  5. **Preservation 5** - Non-credential ``RuntimeError`` (e.g.
     ``RuntimeError("clone failed: exit 128")``) raised inside the
     pipeline passes through the generic ``except Exception`` handler
     unchanged.

Because the preservation surface is large (every successful pipeline
shape, every timeout / cancel path, every non-credential failure), a few
sub-cases use Hypothesis to generate arbitrary payloads and assert the
response mirrors them exactly.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import container.code_mcp_server as code_mcp_server
import container.pipeline as pipeline_module
from container.code_mcp_server import (
    _elicit_with_timeout,
    code,
    connect_git_host,
)
from container.pipeline import run_coding_pipeline


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


_AUTH_URL = "https://github.com/login/device/abc"


def _make_ctx(elicit_side_effect=None, elicit_return_value=None) -> MagicMock:
    """Build a FastMCP-like Context whose ``elicit`` returns or raises.

    ``ctx.elicit`` is an ``AsyncMock`` so it is awaitable. When
    ``elicit_side_effect`` is not ``None`` it wins over
    ``elicit_return_value``. ``report_progress`` is a no-op ``AsyncMock``
    because the pipeline may call it before the elicitation step.
    """
    ctx = MagicMock()
    if elicit_side_effect is not None:
        ctx.elicit = AsyncMock(side_effect=elicit_side_effect)
    else:
        ctx.elicit = AsyncMock(return_value=elicit_return_value)
    ctx.report_progress = AsyncMock(return_value=None)
    ctx.request = None
    return ctx


def _patched_ddb():
    """Context-manager helper: stub the DynamoDB writes the pipeline
    performs so tests never touch AWS."""
    return (
        patch.object(
            pipeline_module, "write_job_record", new=AsyncMock(return_value=None)
        ),
        patch.object(
            pipeline_module, "update_job_status", new=AsyncMock(return_value=None)
        ),
    )


# ---------------------------------------------------------------------------
# Preservation 1 - Successful `code` pipeline mirrors the stubbed result
#
# Preservation clause 3.1: successful invocations with connected git
# credentials complete with ``status == "complete"`` and surface
# ``pr_url`` / ``stop_reason`` / ``files_edited`` from the underlying
# pipeline tools unchanged.
# ---------------------------------------------------------------------------


class TestPreservation1SuccessfulPipelineMirrorsFields:
    """Preservation 1: a successful end-to-end ``code`` invocation
    produces ``status == "complete"`` and mirrors the stubbed
    ``pr_url`` / ``stop_reason`` / ``files_edited`` back to the caller.

    The pipeline's 5 external steps are stubbed so no real git / OAuth /
    OpenCode work happens. The only thing under test is that the shape
    and contents of ``RunPipelineResult`` on the happy path are exactly
    what the tools return.

    **Validates: Requirement 3.1**
    """

    @pytest.mark.asyncio
    async def test_successful_pipeline_example(self) -> None:
        """Example-based test: concrete values pass through unchanged."""
        pr_url = "https://github.com/owner/repo/pull/42"
        stop_reason = "end_turn"
        files_edited = ["README.md", "src/main.py"]

        ctx = _make_ctx()

        opencode_result = {
            "stdout": "",
            "stderr": "",
            "stop_reason": stop_reason,
            "files_edited": files_edited,
            "plan": [],
        }
        push_result = {"pr_url": pr_url, "pushed": True}

        with (
            patch.object(
                pipeline_module,
                "resolve_git_credential",
                return_value={"token": "fake-token"},
            ),
            patch.object(pipeline_module, "git_clone", return_value=None),
            patch.object(
                pipeline_module,
                "run_opencode_acp_impl",
                new=AsyncMock(return_value=opencode_result),
            ),
            patch.object(
                pipeline_module,
                "scan_and_strip_credentials_impl",
                return_value=None,
            ),
            patch.object(
                pipeline_module, "git_push_and_create_pr", return_value=push_result
            ),
            patch("subprocess.run", return_value=MagicMock(returncode=0)),
            patch.object(
                pipeline_module, "write_job_record", new=AsyncMock(return_value=None)
            ),
            patch.object(
                pipeline_module, "update_job_status", new=AsyncMock(return_value=None)
            ),
        ):
            result = await code(
                task_description="add a README",
                repo_url="https://github.com/owner/repo",
                base_branch="main",
                _user_id="user-1",
                ctx=ctx,
            )

        assert result["status"] == "complete"
        assert result["pr_url"] == pr_url
        assert result["stop_reason"] == stop_reason
        assert result["files_edited"] == files_edited
        # error field must be absent on success (TypedDict NotRequired)
        assert "error" not in result
        # duration must be a non-negative float
        assert isinstance(result["duration_seconds"], (int, float))
        assert result["duration_seconds"] >= 0

    @given(
        pr_url=st.text(
            alphabet=st.characters(
                min_codepoint=0x21,
                max_codepoint=0x7E,
                blacklist_characters=" ",
            ),
            min_size=1,
            max_size=80,
        ),
        stop_reason=st.sampled_from(
            ["end_turn", "max_tokens", "max_requests", "refused", "cancelled"]
        ),
        files_edited=st.lists(
            st.text(
                alphabet=st.characters(
                    min_codepoint=0x21,
                    max_codepoint=0x7E,
                    blacklist_characters=" ",
                ),
                min_size=1,
                max_size=40,
            ),
            min_size=0,
            max_size=5,
            unique=True,
        ),
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[
            HealthCheck.too_slow,
            HealthCheck.function_scoped_fixture,
        ],
    )
    def test_successful_pipeline_mirrors_arbitrary_fields(
        self,
        pr_url: str,
        stop_reason: str,
        files_edited: list[str],
    ) -> None:
        """Property test: for any plausible (pr_url, stop_reason,
        files_edited) triple returned by the stubbed pipeline tools, the
        response mirrors them verbatim and sets ``status == "complete"``.
        """

        async def _run() -> dict:
            ctx = _make_ctx()
            opencode_result = {
                "stdout": "",
                "stderr": "",
                "stop_reason": stop_reason,
                "files_edited": list(files_edited),
                "plan": [],
            }
            push_result = {"pr_url": pr_url, "pushed": True}
            with (
                patch.object(
                    pipeline_module,
                    "resolve_git_credential",
                    return_value={"token": "fake-token"},
                ),
                patch.object(pipeline_module, "git_clone", return_value=None),
                patch.object(
                    pipeline_module,
                    "run_opencode_acp_impl",
                    new=AsyncMock(return_value=opencode_result),
                ),
                patch.object(
                    pipeline_module,
                    "scan_and_strip_credentials_impl",
                    return_value=None,
                ),
                patch.object(
                    pipeline_module,
                    "git_push_and_create_pr",
                    return_value=push_result,
                ),
                patch("subprocess.run", return_value=MagicMock(returncode=0)),
                patch.object(
                    pipeline_module,
                    "write_job_record",
                    new=AsyncMock(return_value=None),
                ),
                patch.object(
                    pipeline_module,
                    "update_job_status",
                    new=AsyncMock(return_value=None),
                ),
            ):
                return await code(
                    task_description="task",
                    repo_url="https://github.com/owner/repo",
                    base_branch="main",
                    _user_id="user-1",
                    ctx=ctx,
                )

        result = asyncio.run(_run())

        assert result["status"] == "complete"
        assert result["pr_url"] == pr_url
        assert result["stop_reason"] == stop_reason
        assert result["files_edited"] == list(files_edited)
        assert "error" not in result


# ---------------------------------------------------------------------------
# Preservation 2 - `_elicit_with_timeout` returns None on TimeoutError
#
# Preservation clause 3.7: the existing timeout path is preserved; the
# helper must still return ``None`` when ``ctx.elicit`` raises
# ``asyncio.TimeoutError`` (or the wrapping ``asyncio.wait_for`` raises
# it because the underlying coroutine slept past the timeout).
# ---------------------------------------------------------------------------


class TestPreservation2ElicitWithTimeoutReturnsNoneOnTimeout:
    """Preservation 2: ``_elicit_with_timeout`` returns ``None`` on
    ``asyncio.TimeoutError``.

    Two covering strategies: (a) a direct ``TimeoutError`` side effect,
    and (b) a real elicit coroutine that sleeps past a small timeout
    patched into the module.

    **Validates: Requirement 3.7**
    """

    @pytest.mark.asyncio
    async def test_timeout_error_side_effect_returns_none(self) -> None:
        """When ``ctx.elicit`` raises ``asyncio.TimeoutError`` directly,
        the helper swallows it and returns ``None``."""
        ctx = _make_ctx(elicit_side_effect=asyncio.TimeoutError())
        result = await _elicit_with_timeout(
            ctx,
            message="please confirm",
            schema={"type": "object", "properties": {}},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_sleeping_elicit_triggers_wait_for_timeout(self) -> None:
        """When ``ctx.elicit`` sleeps longer than the configured
        ``ELICITATION_TIMEOUT_S``, ``asyncio.wait_for`` raises
        ``TimeoutError`` and the helper returns ``None``.

        This exercises the actual ``wait_for`` path rather than the
        short-circuit ``side_effect`` path.
        """

        async def _slow_elicit(*_args, **_kwargs) -> object:
            # Sleep well past the patched 0.01s timeout.
            await asyncio.sleep(1.0)
            return {"action": "accept"}

        ctx = MagicMock()
        ctx.elicit = _slow_elicit

        with patch.object(code_mcp_server, "ELICITATION_TIMEOUT_S", 0.01):
            result = await _elicit_with_timeout(
                ctx,
                message="please confirm",
                schema={"type": "object", "properties": {}},
            )

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("timeout_s", [0.01, 0.05, 0.1, 0.25, 0.5])
    async def test_timeout_none_across_range(self, timeout_s: float) -> None:
        """For a range of small but positive timeouts, a sleeping
        ``ctx.elicit`` still yields ``None`` (no accidental
        short-circuit, no exception leak)."""

        async def _slow_elicit(*_args, **_kwargs) -> object:
            await asyncio.sleep(timeout_s + 0.5)
            return {"action": "accept"}

        ctx = MagicMock()
        ctx.elicit = _slow_elicit

        with patch.object(
            code_mcp_server, "ELICITATION_TIMEOUT_S", timeout_s
        ):
            result = await _elicit_with_timeout(
                ctx,
                message="please confirm",
                schema={"type": "object", "properties": {}},
            )

        assert result is None


# ---------------------------------------------------------------------------
# Preservation 3 - User cancel surfaces "OAuth authorization cancelled"
#
# Preservation clause 3.4: when ``ctx.elicit`` returns
# ``result.action == "cancel"``, ``_on_oauth_needed`` returns ``False``,
# which the pipeline translates into
# ``RuntimeError("OAuth authorization cancelled")`` and the generic
# handler surfaces as ``error == "OAuth authorization cancelled"``.
# This message is explicitly out of scope for the fix; it MUST remain
# verbatim.
# ---------------------------------------------------------------------------


class TestPreservation3UserCancelPreservesOAuthCancelledMessage:
    """Preservation 3: a genuine user cancellation still produces
    ``error == "OAuth authorization cancelled"`` - the fix must NOT
    reroute this path through ``GIT_HOST_NOT_CONNECTED_MESSAGE``.

    **Validates: Requirement 3.4**
    """

    @pytest.mark.asyncio
    async def test_user_cancel_yields_oauth_authorization_cancelled(
        self,
    ) -> None:
        """``ctx.elicit`` returns an object with ``action == "cancel"``;
        ``_on_oauth_needed`` returns ``False``; pipeline raises
        ``RuntimeError("OAuth authorization cancelled")``; response
        ``error`` field equals that exact string."""
        cancelled_result = SimpleNamespace(action="cancel")
        ctx = _make_ctx(elicit_return_value=cancelled_result)

        with (
            patch.object(
                pipeline_module,
                "resolve_git_credential",
                return_value={
                    "authorization_required": True,
                    "auth_url": _AUTH_URL,
                },
            ),
            patch.object(
                pipeline_module,
                "write_job_record",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                pipeline_module,
                "update_job_status",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await code(
                task_description="add a README",
                repo_url="https://github.com/owner/repo",
                base_branch="main",
                _user_id="user-1",
                ctx=ctx,
            )

        assert result["status"] == "failed"
        assert result["error"] == "OAuth authorization cancelled"


# ---------------------------------------------------------------------------
# Preservation 4 - `connect_git_host` returns `action_required` on
# elicit failure / None
#
# Preservation clauses 3.6, 3.8: ``connect_git_host`` already wraps
# ``_elicit_with_timeout`` in a ``try/except`` and falls back to a
# structured ``{"status": "action_required", "authorization_url": auth_url}``
# response when elicitation fails. This path is already correct and
# MUST stay byte-for-byte identical after the fix - including when the
# fix makes ``_elicit_with_timeout`` return ``None`` on arbitrary
# exceptions (``connect_git_host`` handles the ``None`` case identically
# to the exception case, so the same structured response is produced).
# ---------------------------------------------------------------------------


class TestPreservation4ConnectGitHostActionRequired:
    """Preservation 4: ``connect_git_host`` falls back to a structured
    ``action_required`` response with the auth URL whenever
    ``_elicit_with_timeout`` returns ``None``.

    **Validates: Requirements 3.6, 3.8**
    """

    @pytest.mark.asyncio
    async def test_action_required_when_elicit_with_timeout_returns_none(
        self,
    ) -> None:
        """Stub ``_get_credential`` to report authorization required
        and ``_elicit_with_timeout`` to return ``None`` (simulating
        either timeout or the post-fix swallowed exception). The
        response is ``{"status": "action_required",
        "authorization_url": "<url>", ...}``.
        """
        with (
            patch.object(
                code_mcp_server,
                "_get_credential",
                return_value=(None, _AUTH_URL),
            ),
            patch.object(
                code_mcp_server,
                "_elicit_with_timeout",
                new=AsyncMock(return_value=None),
            ),
        ):
            ctx = _make_ctx()
            result = await connect_git_host(
                git_host="github.com",
                _user_id="user-1",
                ctx=ctx,
            )

        assert result["status"] == "action_required"
        assert result["authorization_url"] == _AUTH_URL
        assert result["git_host"] == "github.com"
        assert _AUTH_URL in result["message"]

    @given(
        auth_url=st.text(
            alphabet=st.characters(
                min_codepoint=0x21,
                max_codepoint=0x7E,
                blacklist_characters=" ",
            ),
            min_size=10,
            max_size=120,
        ),
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[
            HealthCheck.too_slow,
            HealthCheck.function_scoped_fixture,
        ],
    )
    def test_action_required_for_arbitrary_auth_urls(
        self, auth_url: str
    ) -> None:
        """Property test: for any plausible auth URL string, the
        ``action_required`` response surfaces the URL unchanged in the
        ``authorization_url`` field."""

        async def _run() -> dict:
            with (
                patch.object(
                    code_mcp_server,
                    "_get_credential",
                    return_value=(None, auth_url),
                ),
                patch.object(
                    code_mcp_server,
                    "_elicit_with_timeout",
                    new=AsyncMock(return_value=None),
                ),
            ):
                ctx = _make_ctx()
                return await connect_git_host(
                    git_host="github.com",
                    _user_id="user-1",
                    ctx=ctx,
                )

        result = asyncio.run(_run())

        assert result["status"] == "action_required"
        assert result["authorization_url"] == auth_url


# ---------------------------------------------------------------------------
# Preservation 5 - Non-credential RuntimeErrors pass through unchanged
#
# The design's preservation scope includes "Every non-credential
# pipeline failure (clone errors, OpenCode failures, push failures)".
# The generic ``except Exception`` handler in ``run_coding_pipeline``
# stringifies ``str(exc)[:500]`` into the response's ``error`` field;
# this passthrough MUST be preserved for non-credential errors.
# ---------------------------------------------------------------------------


class TestPreservation5NonCredentialErrorsPassthrough:
    """Preservation 5: a ``RuntimeError`` raised from a non-credential
    step (e.g. ``git_clone``) passes through the generic handler
    byte-for-byte into ``result["error"]``.

    **Validates: Preservation scope from design "Every non-credential
    pipeline failure"**
    """

    @pytest.mark.asyncio
    async def test_clone_failure_passes_through_unchanged(self) -> None:
        """A ``git_clone`` ``RuntimeError`` surfaces in ``result["error"]``
        byte-for-byte."""
        error_message = "clone failed: exit 128"
        ctx = _make_ctx()

        def _raise_clone(*args, **kwargs):
            raise RuntimeError(error_message)

        with (
            patch.object(
                pipeline_module,
                "resolve_git_credential",
                return_value={"token": "fake-token"},
            ),
            patch.object(
                pipeline_module, "git_clone", side_effect=_raise_clone
            ),
            patch("subprocess.run", return_value=MagicMock(returncode=0)),
            patch.object(
                pipeline_module,
                "write_job_record",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                pipeline_module,
                "update_job_status",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await code(
                task_description="add a README",
                repo_url="https://github.com/owner/repo",
                base_branch="main",
                _user_id="user-1",
                ctx=ctx,
            )

        assert result["status"] == "failed"
        assert result["error"] == error_message

    @given(
        error_message=st.text(
            alphabet=st.characters(
                min_codepoint=0x20,
                max_codepoint=0x7E,
                blacklist_characters="\x7f",
            ),
            min_size=1,
            max_size=120,
        ).filter(
            # Avoid accidentally generating the credential-error strings
            # we're testing NOT to produce. Any text that starts with
            # "git_host_not_connected" or "GitHub credentials" would be
            # a false positive for this preservation test.
            lambda s: not s.startswith("git_host_not_connected")
            and not s.startswith("GitHub credentials")
            and s != "OAuth authorization cancelled"
        ),
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[
            HealthCheck.too_slow,
            HealthCheck.function_scoped_fixture,
        ],
    )
    def test_arbitrary_non_credential_runtime_error_passthrough(
        self, error_message: str
    ) -> None:
        """Property test: for any plausible non-credential
        ``RuntimeError`` message, ``result["error"]`` equals that
        message verbatim (subject to the pipeline's ``[:500]`` truncation,
        which is never triggered for our bounded inputs)."""

        def _raise_clone(*args, **kwargs):
            raise RuntimeError(error_message)

        async def _run() -> dict:
            ctx = _make_ctx()
            with (
                patch.object(
                    pipeline_module,
                    "resolve_git_credential",
                    return_value={"token": "fake-token"},
                ),
                patch.object(
                    pipeline_module, "git_clone", side_effect=_raise_clone
                ),
                patch("subprocess.run", return_value=MagicMock(returncode=0)),
                patch.object(
                    pipeline_module,
                    "write_job_record",
                    new=AsyncMock(return_value=None),
                ),
                patch.object(
                    pipeline_module,
                    "update_job_status",
                    new=AsyncMock(return_value=None),
                ),
            ):
                return await code(
                    task_description="task",
                    repo_url="https://github.com/owner/repo",
                    base_branch="main",
                    _user_id="user-1",
                    ctx=ctx,
                )

        result = asyncio.run(_run())

        assert result["status"] == "failed"
        assert result["error"] == error_message[:500]
