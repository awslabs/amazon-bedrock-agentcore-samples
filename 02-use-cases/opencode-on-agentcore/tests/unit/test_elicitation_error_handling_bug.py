# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Bug-condition exploration tests for spec 30-elicitation-error-handling.

These tests encode the *expected* (post-fix) behavior described by
``design.md`` Property 1 and Property 2. Running them against the
UNFIXED tree MUST produce at least one failure per case; each failure
is the counterexample that confirms the corresponding leaky surface
exists.

The three leaky surfaces exercised here (matching ``tasks.md`` task 1):

  * Case A - the sync ``code`` tool surfaces raw ``ctx.elicit`` exceptions
    verbatim when the user is missing git credentials.
  * Case B - ``run_coding_task`` / ``run_coding_pipeline`` with
    ``on_oauth_needed=None`` raises the terse sentinel
    ``RuntimeError("git_host_not_connected")`` instead of the
    user-friendly ``GIT_HOST_NOT_CONNECTED_MESSAGE``.
  * Case C - ``_elicit_with_timeout`` only catches ``asyncio.TimeoutError``
    so any other exception (``TypeError``, ``AttributeError``,
    ``ConnectionError``, ``RuntimeError``) escapes the helper.

These tests intentionally do NOT try to "fix" anything when they fail -
failure is the signal that the bug is present. They will be re-run
post-fix (task 3.5) to confirm every surface has been resolved.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5** (from bugfix.md)
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import container.pipeline as pipeline_module
from container.code_mcp_server import _elicit_with_timeout, code
from container.pipeline import run_coding_pipeline


# ---------------------------------------------------------------------------
# Expected post-fix constant.
#
# ``GIT_HOST_NOT_CONNECTED_MESSAGE`` does not exist yet in the source tree
# (it will be introduced by task 3.1). Define the expected string here
# verbatim from ``bugfix.md`` clause 2.1 so that:
#   * on the UNFIXED tree these tests compare against the post-fix message
#     (and fail, surfacing the raw exception / terse sentinel);
#   * on the FIXED tree, once the production constant exists, the test
#     expectation must match the production constant byte-for-byte.
# ---------------------------------------------------------------------------

GIT_HOST_NOT_CONNECTED_MESSAGE = (
    "GitHub credentials not connected. Run connect_git_host with "
    "git_host='github.com' first, then retry."
)

# Counterexample strings observed on the unfixed tree. Kept here for
# traceability per the ``tasks.md`` "Document the counterexample" bullet.
_UNFIXED_CASE_A_LEAKS = (
    "Context.elicit() got an unexpected keyword argument 'schema'",
    "'Context' object has no attribute 'elicit'",
    "gateway closed",
)
_UNFIXED_CASE_B_LEAK = "git_host_not_connected"


# ---------------------------------------------------------------------------
# Shared pipeline stubs
# ---------------------------------------------------------------------------

_AUTH_URL = "https://github.com/login/device/abc"
_AUTH_REQUIRED_CRED: dict = {
    "authorization_required": True,
    "auth_url": _AUTH_URL,
}


def _make_ctx(elicit_side_effect: BaseException | None = None) -> MagicMock:
    """Build a FastMCP-like Context whose ``elicit`` raises on demand.

    ``ctx.elicit`` is an ``AsyncMock`` so it is awaitable; when
    ``elicit_side_effect`` is not None, awaiting it raises that exception.
    The ``report_progress`` attribute is a no-op ``AsyncMock`` because the
    pipeline may invoke it before the elicitation step.
    """
    ctx = MagicMock()
    ctx.elicit = AsyncMock(side_effect=elicit_side_effect)
    ctx.report_progress = AsyncMock(return_value=None)
    ctx.request = None
    return ctx


# ---------------------------------------------------------------------------
# Case A - ``code`` tool surfaces raw ctx.elicit exceptions
#
# Bug Condition clauses 1.1, 1.2, 1.3:
#   On unfixed code, when ctx.elicit raises a non-timeout exception
#   (TypeError from a FastMCP version mismatch, AttributeError from a
#   missing method, ConnectionError from a transport failure), the raw
#   exception string lands in response["error"] verbatim via the
#   pipeline's generic ``except Exception as exc: error_msg = str(exc)[:500]``
#   branch.
# ---------------------------------------------------------------------------


class TestCaseACodeToolElicitExceptionLeaks:
    """Case A: ``code`` tool must emit ``GIT_HOST_NOT_CONNECTED_MESSAGE``
    even when ``ctx.elicit`` raises ``TypeError`` / ``AttributeError`` /
    ``ConnectionError``.

    On unfixed code, ``_elicit_with_timeout`` only catches
    ``asyncio.TimeoutError``. Any other exception propagates out of
    ``_on_oauth_needed``, is caught by the pipeline's generic handler,
    and the raw ``str(exc)[:500]`` is returned in ``result["error"]``
    - that is the counterexample each parametrised case surfaces.

    **Validates: Requirements 1.1, 1.2, 1.3, 2.1**
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            TypeError(
                "Context.elicit() got an unexpected keyword argument 'schema'"
            ),
            AttributeError("'Context' object has no attribute 'elicit'"),
            ConnectionError("gateway closed"),
        ],
        ids=["type_error", "attribute_error", "connection_error"],
    )
    async def test_code_tool_elicit_non_timeout_exception_returns_user_friendly_error(
        self, exc: BaseException
    ) -> None:
        """Invoke the ``code`` tool, stub ``resolve_git_credential`` to
        report ``authorization_required`` so the OAuth callback fires,
        and stub ``ctx.elicit`` to raise ``exc``.

        Expected post-fix behavior::

            result["status"] == "failed"
            result["error"]  == GIT_HOST_NOT_CONNECTED_MESSAGE

        On unfixed code ``result["error"]`` contains the raw
        ``str(exc)`` (e.g. "Context.elicit() got an unexpected keyword
        argument 'schema'") - this assertion fails, surfacing the bug.
        """
        ctx = _make_ctx(elicit_side_effect=exc)

        # The ``code`` tool flows into ``run_coding_pipeline``, which
        # resolves credentials via ``container.tools.resolve_git_credential``.
        # Stub that to report "authorization needed" so the pipeline
        # invokes the ``_on_oauth_needed`` callback the ``code`` tool
        # registered - that callback in turn awaits ``_elicit_with_timeout``.
        with (
            patch.object(
                pipeline_module,
                "resolve_git_credential",
                return_value=dict(_AUTH_REQUIRED_CRED),
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

        assert result["status"] == "failed", (
            f"Expected status='failed' for exc={exc!r}; got result={result!r}"
        )
        assert result["error"] == GIT_HOST_NOT_CONNECTED_MESSAGE, (
            f"Expected error to equal GIT_HOST_NOT_CONNECTED_MESSAGE for "
            f"exc={exc!r}; got result={result!r}. Counterexample on "
            f"unfixed code: raw exception string str(exc)[:500] leaks "
            f"through the pipeline's generic handler."
        )


# ---------------------------------------------------------------------------
# Case B - ``run_coding_pipeline`` with on_oauth_needed=None
#
# Bug Condition clause 1.4:
#   On unfixed code, the pipeline raises RuntimeError("git_host_not_connected")
#   when credentials are missing and no OAuth callback is available
#   (the async ``run_coding_task`` wiring). The terse sentinel is a leaky
#   internal token; users see it verbatim in their response.
# ---------------------------------------------------------------------------


class TestCaseBRunCodingTaskWithoutCredentials:
    """Case B: ``run_coding_pipeline`` with ``on_oauth_needed=None``
    must emit ``GIT_HOST_NOT_CONNECTED_MESSAGE`` instead of the terse
    ``"git_host_not_connected"`` sentinel.

    **Validates: Requirement 1.4, 2.4**
    """

    @pytest.mark.asyncio
    async def test_run_coding_pipeline_missing_credentials_returns_user_friendly_error(
        self,
    ) -> None:
        """Invoke ``run_coding_pipeline`` directly with
        ``on_oauth_needed=None`` and a stubbed credential resolver that
        reports ``authorization_required``. Expected post-fix behavior::

            result["status"] == "failed"
            result["error"]  == GIT_HOST_NOT_CONNECTED_MESSAGE

        On unfixed code ``result["error"] == "git_host_not_connected"``
        - the terse internal sentinel leaks verbatim through the
        pipeline's generic handler.
        """
        with (
            patch.object(
                pipeline_module,
                "resolve_git_credential",
                return_value=dict(_AUTH_REQUIRED_CRED),
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
            result = await run_coding_pipeline(
                user_id="user-1",
                job_id="job-1",
                task_description="add a README",
                repo_url="https://github.com/owner/repo",
                base_branch="main",
                target_branch="opencode/job-1",
                work_dir="/tmp/pipeline-30-bug/job-1",
                timeout_minutes=10,
                metric_prefix="async_task",
                on_progress=None,
                on_oauth_needed=None,
                cancel_flag=None,
            )

        assert result["status"] == "failed", (
            f"Expected status='failed'; got result={result!r}"
        )
        assert result["error"] == GIT_HOST_NOT_CONNECTED_MESSAGE, (
            f"Expected error to equal GIT_HOST_NOT_CONNECTED_MESSAGE; "
            f"got result={result!r}. Counterexample on unfixed code: "
            f"error == {_UNFIXED_CASE_B_LEAK!r}."
        )


# ---------------------------------------------------------------------------
# Case C - ``_elicit_with_timeout`` leaks non-timeout exceptions
#
# Bug Condition clause 1.5:
#   On unfixed code the helper only catches ``asyncio.TimeoutError``. Any
#   other exception class (TypeError, AttributeError, ConnectionError,
#   RuntimeError, ...) propagates out of the helper unchanged. The
#   enumerated four cover the FastMCP version-mismatch, missing-method,
#   transport-failure, and generic-runtime-error shapes respectively.
#
# A scoped Hypothesis strategy enumerates the four classes so each
# branch is exercised with a unique message without fabricating
# implausible exception subclasses.
# ---------------------------------------------------------------------------


_NON_TIMEOUT_EXCEPTION_CLASSES = st.sampled_from(
    [TypeError, AttributeError, ConnectionError, RuntimeError]
)


@st.composite
def _non_timeout_exception_instance(draw: st.DrawFn) -> BaseException:
    """Generate one exception instance from the four enumerated classes."""
    cls = draw(_NON_TIMEOUT_EXCEPTION_CLASSES)
    message = draw(
        st.text(
            alphabet=st.characters(
                min_codepoint=0x20,
                max_codepoint=0x7E,
                blacklist_characters="\x7f",
            ),
            min_size=1,
            max_size=64,
        )
    )
    return cls(message)


class TestCaseCElicitWithTimeoutNonTimeoutException:
    """Case C: ``_elicit_with_timeout`` must catch every non-timeout
    exception from ``ctx.elicit`` and return ``None``, logging a WARNING
    record with ``exc_info`` set.

    On unfixed code, ``_elicit_with_timeout`` only catches
    ``asyncio.TimeoutError`` - every other exception escapes the helper.
    The post-fix contract (per Property 2 in ``design.md``) is::

        _elicit_with_timeout returns None
        caplog contains a WARNING record with exc_info

    **Validates: Requirements 1.5, 2.3, 2.5**
    """

    # Enumerated parametrised cases keep the failure signal obvious for
    # each of the four exception classes called out in the task brief.
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            TypeError(
                "Context.elicit() got an unexpected keyword argument 'schema'"
            ),
            AttributeError("'Context' object has no attribute 'elicit'"),
            ConnectionError("gateway closed"),
            RuntimeError("elicitation backend exploded"),
        ],
        ids=[
            "type_error",
            "attribute_error",
            "connection_error",
            "runtime_error",
        ],
    )
    async def test_non_timeout_exception_caught_and_logged(
        self,
        exc: BaseException,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Awaiting ``_elicit_with_timeout`` when ``ctx.elicit`` raises
        ``exc`` must return ``None`` AND emit a WARNING log record with
        ``exc_info`` set.

        On unfixed code the exception propagates out of the helper -
        the first assertion never runs because the coroutine raises.
        """
        ctx = _make_ctx(elicit_side_effect=exc)

        with caplog.at_level(
            logging.WARNING, logger="container.code_mcp_server"
        ):
            result = await _elicit_with_timeout(
                ctx,
                message="test prompt",
                schema={"type": "object", "properties": {}},
            )

        assert result is None, (
            f"Expected _elicit_with_timeout to return None when "
            f"ctx.elicit raised {exc!r}; got {result!r}. Counterexample "
            f"on unfixed code: the exception propagates out of the helper."
        )

        warning_records = [
            r for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert warning_records, (
            f"Expected at least one WARNING log record for exc={exc!r}; "
            f"caplog records={caplog.records!r}"
        )
        assert any(r.exc_info for r in warning_records), (
            f"Expected at least one WARNING record with exc_info set for "
            f"exc={exc!r}; got warning_records={warning_records!r}"
        )

    @given(exc=_non_timeout_exception_instance())
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[
            HealthCheck.too_slow,
            HealthCheck.function_scoped_fixture,
        ],
    )
    def test_non_timeout_exception_property(
        self, exc: BaseException
    ) -> None:
        """Property-based variant: for any instance of the four
        enumerated non-timeout exception classes,
        ``_elicit_with_timeout`` must return ``None``.

        On unfixed code the helper re-raises the exception instead of
        returning ``None``; this property therefore fails on every
        drawn example.
        """

        async def _run() -> object:
            ctx = _make_ctx(elicit_side_effect=exc)
            return await _elicit_with_timeout(
                ctx,
                message="test prompt",
                schema={"type": "object", "properties": {}},
            )

        result = asyncio.run(_run())

        assert result is None, (
            f"Expected _elicit_with_timeout to return None when "
            f"ctx.elicit raised {exc!r}; got {result!r}."
        )
