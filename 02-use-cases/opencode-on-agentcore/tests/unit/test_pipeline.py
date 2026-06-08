# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Example-based unit tests for ``container.pipeline.run_coding_pipeline``.

Feature: pipeline-extraction-refactor

These tests cover the happy path under the two callback configurations
used by the Sync_Tool (``code``) and Async_Tool (``run_coding_task``) MCP
handlers. They complement the Hypothesis property tests in
``tests/property/test_pipeline_properties.py`` by pinning specific,
human-readable example scenarios that a failing property test might
otherwise obscure.

The tests reuse ``PipelineRecorder`` from the property test module so the
patch set-up is identical to (and kept in sync with) the property tests.
This is safe because ``PipelineRecorder`` is defined at module scope in
``tests/property/test_pipeline_properties.py`` and re-exported via
``__all__``; importing it does not trigger any property-test
``@given`` collection.

Design references:
    - ``design.md § Sequence: Sync Path (via callbacks)``
    - ``design.md § Sequence: Async Path (via callbacks)``
    - ``requirements.md § Requirement 3`` (sync/async parity)
    - ``requirements.md § Requirement 4`` (progress callback isolation)
    - ``requirements.md § Requirement 8`` (metric prefix)
    - ``requirements.md § Requirement 14.4`` (example-based unit coverage)
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

import container.pipeline as pipeline_module
from container.lib.credential_errors import GIT_HOST_NOT_CONNECTED_MESSAGE
from container.pipeline import run_coding_pipeline
from tests.property.test_pipeline_properties import PipelineRecorder


# ---------------------------------------------------------------------------
# Fixed example inputs
#
# The two happy-path tests below use the same concrete values so that the
# sync and async runs exercise identical pipeline inputs; the only thing
# that varies is the callback configuration.
# ---------------------------------------------------------------------------

_USER_ID = "u1"
_JOB_ID = "j1"
_TASK_DESCRIPTION = "Add a README"
_REPO_URL = "https://github.com/owner/repo"
_BASE_BRANCH = "main"
_TARGET_BRANCH = "opencode/j1"
_WORK_DIR = "/tmp/pipeline-unit/j1"
_TIMEOUT_MINUTES = 10

#: Expected ordered sequence of step-function invocations on the success path.
_EXPECTED_STEP_ORDER: list[str] = [
    "resolve_git_credential",
    "git_clone",
    "run_opencode_acp_impl",
    "scan_and_strip_credentials_impl",
    "git_push_and_create_pr",
]

#: Expected ordered sequence of phase-message strings (design.md § Sequence:
#: Sync Path, Requirement 3.5).
_EXPECTED_PROGRESS_MESSAGES: list[str] = [
    "Cloning repository...",
    "Running OpenCode...",
    "Scanning for credentials...",
    "Pushing changes...",
    "Done",
]


@pytest.mark.asyncio
async def test_happy_path_sync_style_callbacks() -> None:
    """Sync_Tool-style callback configuration on the success path.

    **Validates: Requirements 3.1, 3.2, 3.5, 4.2, 4.3, 4.4, 8.1, 8.4**

    Mirrors the ``code`` MCP tool's wiring:

    - ``on_progress`` is an async closure that records each phase event.
    - ``on_oauth_needed`` is provided but not invoked on the happy path.
    - ``cancel_flag`` is ``None`` (sync tool cannot be cancelled).
    - ``metric_prefix`` is ``"code"``.

    Asserts:

    1. The returned Result_Dict has ``status == "complete"``.
    2. Exactly five progress events are emitted with
       ``progress=[1, 2, 3, 4, 5]``, ``total=5``, and the fixed phase
       messages from Requirement 3.5.
    3. The five step functions run in the documented order.
    4. DynamoDB transitions ``RUNNING -> COMPLETE``.
    5. Exactly one ``code.success`` counter and one ``code.duration``
       histogram are emitted; no other metrics are emitted.
    """
    progress_events: list[tuple[int, int, str]] = []

    async def _on_progress(progress: int, total: int, message: str) -> None:
        progress_events.append((progress, total, message))

    oauth_calls: list[str] = []

    async def _on_oauth_needed(auth_url: str) -> bool:
        # Provided to mirror the sync tool's wiring; never invoked when
        # ``resolve_git_credential`` returns a token on the first call
        # (the default behavior of ``PipelineRecorder``).
        oauth_calls.append(auth_url)
        return True

    recorder = PipelineRecorder()
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=_on_progress,
            on_oauth_needed=_on_oauth_needed,
            cancel_flag=None,
            metric_prefix="code",
        )

    # ---------------- Result_Dict ----------------
    assert result["status"] == "complete", (
        f"Expected successful completion, got result={result!r}"
    )

    # ---------------- Progress events ----------------
    # Requirement 4.2 / 4.3 / 4.4 / 3.5: 5 events, progress=[1..5], total=5,
    # messages in the fixed order.
    assert len(progress_events) == 5, (
        f"Expected 5 progress events, got {len(progress_events)}: "
        f"{progress_events!r}"
    )
    assert [p for p, _t, _m in progress_events] == [1, 2, 3, 4, 5]
    assert all(t == 5 for _p, t, _m in progress_events)
    assert [m for _p, _t, m in progress_events] == _EXPECTED_PROGRESS_MESSAGES

    # ---------------- OAuth callback ----------------
    # Happy path: no OAuth challenge was simulated, so the callback must
    # not have been invoked.
    assert oauth_calls == [], (
        f"on_oauth_needed should not have been invoked on the happy path; "
        f"got calls={oauth_calls!r}"
    )

    # ---------------- Step call ordering ----------------
    step_names = [call.name for call in recorder.step_calls]
    assert step_names == _EXPECTED_STEP_ORDER, (
        f"Step functions were not invoked in the documented order: "
        f"got {step_names!r}, expected {_EXPECTED_STEP_ORDER!r}"
    )

    # ---------------- DynamoDB transition ----------------
    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "COMPLETE"], (
        f"Expected DDB transition RUNNING -> COMPLETE, got {ddb_statuses!r}"
    )

    # ---------------- Metrics ----------------
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.success"], (
        f"Expected exactly one code.success counter, got {metric_names!r}"
    )

    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == ["code.duration"], (
        f"Expected exactly one code.duration histogram, got "
        f"{histogram_names!r}"
    )


@pytest.mark.asyncio
async def test_happy_path_async_style_callbacks() -> None:
    """Async_Tool-style callback configuration on the success path.

    **Validates: Requirements 3.1, 3.2, 4.1, 8.2, 8.5**

    Mirrors the ``run_coding_task`` MCP tool's wiring:

    - ``on_progress`` is ``None`` (no client subscribed for streaming).
    - ``on_oauth_needed`` is ``None`` (async tool fails fast on OAuth).
    - ``cancel_flag`` is ``lambda: False`` (never requesting cancel).
    - ``metric_prefix`` is ``"async_task"``.

    Asserts:

    1. The returned Result_Dict has ``status == "complete"``.
    2. No progress events are emitted (trivially; no closure passed).
    3. The five step functions run in the documented order.
    4. DynamoDB transitions ``RUNNING -> COMPLETE``.
    5. Exactly one ``async_task.success`` counter and one
       ``async_task.duration`` histogram are emitted; no other metrics
       are emitted.
    """
    recorder = PipelineRecorder()
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=lambda: False,
            metric_prefix="async_task",
        )

    # ---------------- Result_Dict ----------------
    assert result["status"] == "complete", (
        f"Expected successful completion, got result={result!r}"
    )

    # ---------------- Step call ordering ----------------
    step_names = [call.name for call in recorder.step_calls]
    assert step_names == _EXPECTED_STEP_ORDER, (
        f"Step functions were not invoked in the documented order: "
        f"got {step_names!r}, expected {_EXPECTED_STEP_ORDER!r}"
    )

    # ---------------- DynamoDB transition ----------------
    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "COMPLETE"], (
        f"Expected DDB transition RUNNING -> COMPLETE, got {ddb_statuses!r}"
    )

    # ---------------- Metrics ----------------
    # Requirement 8.2: when metric_prefix="async_task", emitted metric
    # names are drawn exclusively from the async_task.* set. This test
    # asserts the exact happy-path subset.
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["async_task.success"], (
        f"Expected exactly one async_task.success counter, got "
        f"{metric_names!r}"
    )

    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == ["async_task.duration"], (
        f"Expected exactly one async_task.duration histogram, got "
        f"{histogram_names!r}"
    )


# ---------------------------------------------------------------------------
# OAuth unit tests (Requirement 6 cases 1-4)
#
# These tests pin the four OAuth exit paths documented in
# ``requirements.md § Requirement 6`` and
# ``design.md § Error Classification Table`` rows 1-3 (plus the happy-path
# OAuth retry case). They reuse the same fixed example inputs as the happy-
# path tests so the OAuth divergence is the only variable across runs.
#
# The fixtures below intentionally use short literal strings (not the URLs
# in the property test's ``_OAUTH_AUTH_REQUIRED``) because these unit tests
# are a pinned, human-readable counterpart to the property test's exhaustive
# coverage and benefit from minimal-to-read values.
# ---------------------------------------------------------------------------


_OAUTH_AUTH_REQUIRED: dict[str, object] = {
    "authorization_required": True,
    "auth_url": "https://example/oauth",
}

_OAUTH_VALID_CRED: dict[str, object] = {"token": "t"}


@pytest.mark.asyncio
async def test_oauth_case_1_none_callback() -> None:
    """OAuth Case 1: ``authorization_required=True`` with ``on_oauth_needed=None``.

    **Validates: Requirements 6.1, 6.5, 6.6**

    When ``resolve_git_credential`` returns ``{"authorization_required":
    True, ...}`` on its first call and ``on_oauth_needed`` is ``None``,
    the pipeline must fail fast with
    ``error=GIT_HOST_NOT_CONNECTED_MESSAGE`` and must have called
    ``resolve_git_credential`` exactly once (no retry is attempted
    because there is no callback to elicit OAuth confirmation).

    After spec 30 (elicitation-error-handling), the terse internal
    sentinel ``"git_host_not_connected"`` was replaced by the shared
    user-facing ``GIT_HOST_NOT_CONNECTED_MESSAGE`` constant so every
    credential-missing surface emits the same actionable message.
    """
    recorder = PipelineRecorder(cred_results=[dict(_OAUTH_AUTH_REQUIRED)])
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert result.get("error") == GIT_HOST_NOT_CONNECTED_MESSAGE, (
        f"Expected error=GIT_HOST_NOT_CONNECTED_MESSAGE, got result={result!r}"
    )

    cred_calls = sum(
        1
        for call in recorder.step_calls
        if call.name == "resolve_git_credential"
    )
    assert cred_calls == 1, (
        f"Expected resolve_git_credential called exactly once, got "
        f"{cred_calls}"
    )


@pytest.mark.asyncio
async def test_oauth_case_2_cancelled_callback() -> None:
    """OAuth Case 2: callback returns ``False`` (user cancelled elicitation).

    **Validates: Requirements 6.2, 6.5, 6.6**

    When ``resolve_git_credential`` returns ``authorization_required=True``
    on its first call and ``on_oauth_needed`` returns ``False``, the
    pipeline must fail with ``error="OAuth authorization cancelled"``,
    must have called ``resolve_git_credential`` exactly once (no retry
    attempted because the user declined), and must have called
    ``on_oauth_needed`` exactly once.
    """
    oauth_calls: list[str] = []

    async def _on_oauth_needed(auth_url: str) -> bool:
        oauth_calls.append(auth_url)
        return False

    recorder = PipelineRecorder(cred_results=[dict(_OAUTH_AUTH_REQUIRED)])
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=_on_oauth_needed,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert result.get("error") == "OAuth authorization cancelled", (
        f"Expected error='OAuth authorization cancelled', got "
        f"result={result!r}"
    )

    cred_calls = sum(
        1
        for call in recorder.step_calls
        if call.name == "resolve_git_credential"
    )
    assert cred_calls == 1, (
        f"Expected resolve_git_credential called exactly once, got "
        f"{cred_calls}"
    )
    assert len(oauth_calls) == 1, (
        f"Expected on_oauth_needed called exactly once, got "
        f"{len(oauth_calls)}: {oauth_calls!r}"
    )


@pytest.mark.asyncio
async def test_oauth_case_3_confirmed_valid_retry() -> None:
    """OAuth Case 3: callback returns ``True`` and the retry succeeds.

    **Validates: Requirements 6.3, 6.5, 6.6**

    When ``resolve_git_credential`` returns ``authorization_required=True``
    on its first call, ``on_oauth_needed`` returns ``True``, and
    ``resolve_git_credential`` returns a valid credential on its second
    call, the pipeline must proceed through all five Step_Functions
    (with ``resolve_git_credential`` invoked twice in total) and must
    have called ``on_oauth_needed`` exactly once.
    """
    oauth_calls: list[str] = []

    async def _on_oauth_needed(auth_url: str) -> bool:
        oauth_calls.append(auth_url)
        return True

    recorder = PipelineRecorder(
        cred_results=[dict(_OAUTH_AUTH_REQUIRED), dict(_OAUTH_VALID_CRED)]
    )
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=_on_oauth_needed,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "complete", (
        f"Expected status='complete' after successful OAuth retry, got "
        f"result={result!r}"
    )

    cred_calls = sum(
        1
        for call in recorder.step_calls
        if call.name == "resolve_git_credential"
    )
    assert cred_calls == 2, (
        f"Expected resolve_git_credential called exactly twice "
        f"(initial + retry), got {cred_calls}"
    )
    assert len(oauth_calls) == 1, (
        f"Expected on_oauth_needed called exactly once, got "
        f"{len(oauth_calls)}: {oauth_calls!r}"
    )

    # Pipeline proceeded through all 5 Step_Functions. Total recorded
    # step calls is 6 because ``resolve_git_credential`` was invoked
    # twice (initial + retry).
    observed_step_names = [call.name for call in recorder.step_calls]
    assert observed_step_names == [
        "resolve_git_credential",
        "resolve_git_credential",
        "git_clone",
        "run_opencode_acp_impl",
        "scan_and_strip_credentials_impl",
        "git_push_and_create_pr",
    ], (
        f"Step call sequence did not match the documented order with "
        f"a single OAuth retry; got {observed_step_names!r}"
    )


@pytest.mark.asyncio
async def test_oauth_case_4_confirmed_unauthorized_retry() -> None:
    """OAuth Case 4: callback returns ``True`` but retry is still unauthorized.

    **Validates: Requirements 6.4, 6.5, 6.6**

    When ``resolve_git_credential`` returns ``authorization_required=True``
    on both the initial and retry calls and ``on_oauth_needed`` returns
    ``True``, the pipeline must fail with
    ``error="Git host not connected after OAuth attempt"`` and must have
    called ``resolve_git_credential`` exactly twice (the upper bound
    imposed by Requirement 6.5).
    """
    oauth_calls: list[str] = []

    async def _on_oauth_needed(auth_url: str) -> bool:
        oauth_calls.append(auth_url)
        return True

    recorder = PipelineRecorder(
        cred_results=[dict(_OAUTH_AUTH_REQUIRED), dict(_OAUTH_AUTH_REQUIRED)]
    )
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=_on_oauth_needed,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert (
        result.get("error") == "Git host not connected after OAuth attempt"
    ), (
        f"Expected error='Git host not connected after OAuth attempt', "
        f"got result={result!r}"
    )

    cred_calls = sum(
        1
        for call in recorder.step_calls
        if call.name == "resolve_git_credential"
    )
    assert cred_calls == 2, (
        f"Expected resolve_git_credential called exactly twice "
        f"(initial + retry), got {cred_calls}"
    )
    assert len(oauth_calls) == 1, (
        f"Expected on_oauth_needed called exactly once, got "
        f"{len(oauth_calls)}: {oauth_calls!r}"
    )


# ---------------------------------------------------------------------------
# Per-step failure unit tests (Task 3.3, rows 4-10 of the error
# classification table in ``design.md``).
#
# Each test injects a single exception via the corresponding
# ``PipelineRecorder`` side-effect kwarg and asserts the Row-N behavior
# from ``design.md § Error Classification Table``:
#
#   * DynamoDB terminal write is ``FAILED`` (``RUNNING -> FAILED``).
#   * Exactly one counter metric ``{metric_prefix}.failure`` is emitted.
#   * No histogram is emitted on the failure path (Requirement 7.4).
#   * The returned Result_Dict has ``status="failed"`` and
#     ``error == str(exc)`` (exception message < 500 chars so truncation
#     is not exercised here; Property 7 covers truncation).
#
# Rows 5 and 6 (``git_clone`` vs. ``git config`` / ``git checkout -b``)
# collapse into a single unit-test case because ``PipelineRecorder``
# patches the top-level ``git_clone`` function rather than the
# ``subprocess.run`` calls for ``git config`` / ``git checkout -b`` that
# live inside the pipeline body. Rows 7 and 8 (``run_opencode_acp_impl``
# RuntimeError vs. timeout) are both exercised by injecting different
# RuntimeError messages into the same step function. Row 11
# (``git_push_and_create_pr`` returning ``pr_url=None``) is covered by
# the final test in this section, which asserts the pipeline treats that
# return as a success with ``pr_url=""``.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step_failure_resolve_git_credential_raises() -> None:
    """Row 4: ``resolve_git_credential`` raises a non-OAuth exception.

    **Validates: Requirements 10.1, 7.1, 7.2, 7.4, 7.5, 9.7**

    When ``resolve_git_credential`` raises an exception that is not the
    ``authorization_required`` logical case handled by Requirement 6,
    the pipeline must:

    1. Write DynamoDB terminal status ``FAILED``
       (``RUNNING -> FAILED``).
    2. Emit exactly one ``{metric_prefix}.failure`` counter metric.
    3. Emit no ``{metric_prefix}.duration`` histogram.
    4. Return a Result_Dict with ``status="failed"`` and
       ``error=str(exc)``.
    """
    exc = RuntimeError("boto error")
    recorder = PipelineRecorder(cred_side_effect=exc)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    # ---------------- Result_Dict ----------------
    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert result["error"] == str(exc), (
        f"Expected error={str(exc)!r}, got result={result!r}"
    )

    # ---------------- DynamoDB transition ----------------
    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "FAILED"], (
        f"Expected DDB transition RUNNING -> FAILED, got {ddb_statuses!r}"
    )

    # ---------------- Metrics ----------------
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.failure"], (
        f"Expected exactly one code.failure counter, got {metric_names!r}"
    )

    # Requirement 7.4: no histogram on the failure path.
    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"Expected no histogram events on failure, got {histogram_names!r}"
    )


@pytest.mark.asyncio
async def test_step_failure_git_clone_raises() -> None:
    """Rows 5 and 6: ``git_clone`` raises ``subprocess.CalledProcessError``.

    **Validates: Requirements 10.2, 7.1, 7.2, 7.4, 7.5, 9.7**

    When ``git_clone`` (or any of ``git config user.email`` / ``git
    config user.name`` / ``git checkout -b``) raises
    ``subprocess.CalledProcessError``, the pipeline must write
    DynamoDB terminal status ``FAILED``, emit
    ``{metric_prefix}.failure``, and return ``status="failed"`` with
    ``error=str(exc)``.

    ``PipelineRecorder`` patches the top-level ``git_clone`` function
    rather than ``subprocess.run``, so Rows 5 and 6 of the error
    classification table collapse into a single unit test at this level;
    the distinction is preserved in the requirements table for design
    traceability.
    """
    exc = subprocess.CalledProcessError(1, "git clone")
    recorder = PipelineRecorder(clone_side_effect=exc)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert result["error"] == str(exc), (
        f"Expected error={str(exc)!r}, got result={result!r}"
    )

    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "FAILED"], (
        f"Expected DDB transition RUNNING -> FAILED, got {ddb_statuses!r}"
    )

    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.failure"], (
        f"Expected exactly one code.failure counter, got {metric_names!r}"
    )

    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"Expected no histogram events on failure, got {histogram_names!r}"
    )


@pytest.mark.asyncio
async def test_step_failure_run_opencode_acp_raises_runtime_error() -> None:
    """Row 7: ``run_opencode_acp_impl`` raises a ``RuntimeError`` (ACP error).

    **Validates: Requirements 10.3, 7.1, 7.2, 7.4, 7.5, 9.7**

    When ``run_opencode_acp_impl`` raises an ACP-protocol
    ``RuntimeError`` (non-zero exit from the OpenCode subprocess), the
    pipeline must write ``FAILED``, emit ``code.failure``, and return
    ``status="failed"`` with ``error=str(exc)``.
    """
    exc = RuntimeError("ACP protocol error")
    recorder = PipelineRecorder(opencode_side_effect=exc)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert result["error"] == str(exc), (
        f"Expected error={str(exc)!r}, got result={result!r}"
    )

    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "FAILED"], (
        f"Expected DDB transition RUNNING -> FAILED, got {ddb_statuses!r}"
    )

    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.failure"], (
        f"Expected exactly one code.failure counter, got {metric_names!r}"
    )

    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"Expected no histogram events on failure, got {histogram_names!r}"
    )


@pytest.mark.asyncio
async def test_step_failure_run_opencode_acp_raises_timeout() -> None:
    """Row 8: ``run_opencode_acp_impl`` raises a timeout ``RuntimeError``.

    **Validates: Requirements 10.3, 7.1, 7.2, 7.4, 7.5, 9.7**

    When ``run_opencode_acp_impl`` raises
    ``RuntimeError("OpenCode timed out after ...")``, the pipeline
    must classify it identically to Row 7: write ``FAILED``, emit
    ``code.failure``, and return ``status="failed"`` with
    ``error=str(exc)``. This test exercises the timeout message shape
    explicitly because it is the most common OpenCode failure mode in
    production.
    """
    exc = RuntimeError("OpenCode timed out after 600s")
    recorder = PipelineRecorder(opencode_side_effect=exc)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert result["error"] == str(exc), (
        f"Expected error={str(exc)!r}, got result={result!r}"
    )

    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "FAILED"], (
        f"Expected DDB transition RUNNING -> FAILED, got {ddb_statuses!r}"
    )

    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.failure"], (
        f"Expected exactly one code.failure counter, got {metric_names!r}"
    )

    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"Expected no histogram events on failure, got {histogram_names!r}"
    )


@pytest.mark.asyncio
async def test_step_failure_scan_and_strip_credentials_raises() -> None:
    """Row 9: ``scan_and_strip_credentials_impl`` raises (file I/O, etc.).

    **Validates: Requirements 10.4, 7.1, 7.2, 7.4, 7.5, 9.7**

    When ``scan_and_strip_credentials_impl`` raises any exception
    (typical cause: file I/O error while scanning the work directory),
    the pipeline must write ``FAILED``, emit ``code.failure``, and
    return ``status="failed"`` with ``error=str(exc)``.
    """
    exc = OSError("file not found")
    recorder = PipelineRecorder(scan_side_effect=exc)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert result["error"] == str(exc), (
        f"Expected error={str(exc)!r}, got result={result!r}"
    )

    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "FAILED"], (
        f"Expected DDB transition RUNNING -> FAILED, got {ddb_statuses!r}"
    )

    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.failure"], (
        f"Expected exactly one code.failure counter, got {metric_names!r}"
    )

    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"Expected no histogram events on failure, got {histogram_names!r}"
    )


@pytest.mark.asyncio
async def test_step_failure_git_push_raises_after_retries() -> None:
    """Row 10: ``git_push_and_create_pr`` raises after exhausting retries.

    **Validates: Requirements 10.5, 10.7, 7.1, 7.2, 7.4, 7.5, 9.7**

    When ``git_push_and_create_pr`` raises
    ``subprocess.CalledProcessError`` after its internal 3-attempt
    rebase-on-latest retry loop has been exhausted, the pipeline must
    write ``FAILED``, emit ``code.failure``, and return
    ``status="failed"`` with ``error=str(exc)``. The pipeline itself
    must not introduce any additional retry layer (Requirement 10.7);
    the unit test mirrors this by injecting a single terminal exception
    from the step function.
    """
    exc = subprocess.CalledProcessError(1, "git push")
    recorder = PipelineRecorder(push_side_effect=exc)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    assert result["status"] == "failed", (
        f"Expected status='failed', got result={result!r}"
    )
    assert result["error"] == str(exc), (
        f"Expected error={str(exc)!r}, got result={result!r}"
    )

    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "FAILED"], (
        f"Expected DDB transition RUNNING -> FAILED, got {ddb_statuses!r}"
    )

    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.failure"], (
        f"Expected exactly one code.failure counter, got {metric_names!r}"
    )

    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"Expected no histogram events on failure, got {histogram_names!r}"
    )


@pytest.mark.asyncio
async def test_git_push_returns_none_pr_url_is_success() -> None:
    """Row 11: ``git_push_and_create_pr`` returns ``pr_url=None`` -> success.

    **Validates: Requirements 10.6, 7.1, 7.2, 7.3, 7.5, 9.4**

    When ``git_push_and_create_pr`` returns successfully with
    ``pr_url=None`` (no diff to push, or PR-creation API failure after
    a successful push), the pipeline must treat the run as
    **successful**:

    1. Result_Dict ``status == "complete"`` and ``pr_url == ""``
       (empty string, not ``None``).
    2. DynamoDB terminal write is ``COMPLETE``
       (``RUNNING -> COMPLETE``).
    3. Exactly one ``code.success`` counter is emitted.
    4. The ``code.duration`` histogram IS emitted (Requirement 7.3).
    """
    recorder = PipelineRecorder(push_result={"pr_url": None, "pushed": True})
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    # ---------------- Result_Dict ----------------
    assert result["status"] == "complete", (
        f"Expected status='complete' when pr_url is None, "
        f"got result={result!r}"
    )
    assert result.get("pr_url") == "", (
        f"Expected pr_url='' (empty string) when push returned pr_url=None, "
        f"got result={result!r}"
    )

    # ---------------- DynamoDB transition ----------------
    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "COMPLETE"], (
        f"Expected DDB transition RUNNING -> COMPLETE, got {ddb_statuses!r}"
    )

    # ---------------- Metrics ----------------
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.success"], (
        f"Expected exactly one code.success counter, got {metric_names!r}"
    )

    # Requirement 7.3: duration histogram IS emitted on the success path.
    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == ["code.duration"], (
        f"Expected exactly one code.duration histogram, got "
        f"{histogram_names!r}"
    )


# ---------------------------------------------------------------------------
# Per-check-point cancellation unit tests (Task 3.4).
#
# Cover each of the five Cancellation Check_Points documented in
# ``design.md § Cancellation Check-point Semantics`` / Requirement 5. One
# parametrized test case per ``k in [1, 2, 3, 4, 5]``: the ``cancel_flag``
# closure returns ``True`` on its ``k``-th poll, causing the pipeline to
# raise ``asyncio.CancelledError`` immediately before Step_Function ``k``
# begins. The pipeline must:
#
#   1. Invoke Step_Functions ``1`` through ``k-1`` exactly once each,
#      in the documented order (Requirement 5.4).
#   2. NOT invoke Step_Functions ``k`` through ``5``
#      (Requirement 5.3).
#   3. Write DynamoDB terminal status ``CANCELLED``
#      (``RUNNING -> CANCELLED``) exactly once
#      (Requirements 5.6, 7.1, 7.5).
#   4. Emit exactly one ``{metric_prefix}.cancelled`` counter metric
#      (Requirements 5.6, 7.2).
#   5. NOT emit the ``{metric_prefix}.duration`` histogram
#      (Requirement 7.4).
#   6. Return a Result_Dict with ``status="cancelled"`` and
#      ``error="Task cancelled"`` (Requirement 9.6).
#
# The async path is the only caller that passes a non-``None``
# ``cancel_flag`` (the sync ``code`` tool passes ``None``; see
# Requirement 5.2), so these tests use ``metric_prefix="async_task"`` to
# mirror production wiring.
# ---------------------------------------------------------------------------


#: The ordered prefix of Step_Function names that must have run before
#: Check_Point ``k`` fires. Indexing is 1-based to match the check-point
#: numbering in ``design.md``; ``_STEPS_BEFORE_CHECKPOINT[k]`` is the list
#: of step names that completed before the ``k``-th cancel poll.
_STEPS_BEFORE_CHECKPOINT: dict[int, list[str]] = {
    1: [],
    2: ["resolve_git_credential"],
    3: ["resolve_git_credential", "git_clone"],
    4: [
        "resolve_git_credential",
        "git_clone",
        "run_opencode_acp_impl",
    ],
    5: [
        "resolve_git_credential",
        "git_clone",
        "run_opencode_acp_impl",
        "scan_and_strip_credentials_impl",
    ],
}


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5])
@pytest.mark.asyncio
async def test_cancellation_at_checkpoint_k(k: int) -> None:
    """Cancellation at Check_Point ``k`` for ``k in [1, 2, 3, 4, 5]``.

    **Validates: Requirements 5.1, 5.3, 5.4, 5.6, 7.1, 7.2, 7.4, 7.5, 9.6**

    The ``cancel_flag`` closure returns ``False`` on its first ``k-1``
    polls and ``True`` on its ``k``-th poll (the poll immediately
    preceding Step_Function ``k``). The pipeline must raise
    ``asyncio.CancelledError`` before Step_Function ``k`` begins and
    short-circuit into the cancellation terminal path.

    Asserts:

    1. Result_Dict ``status == "cancelled"`` and
       ``error == "Task cancelled"``.
    2. Step_Functions ``1..k-1`` ran in the documented order;
       Step_Functions ``k..5`` did not run at all.
    3. DynamoDB transition is ``RUNNING -> CANCELLED``.
    4. Exactly one ``async_task.cancelled`` counter metric is emitted.
    5. No histogram event is emitted (Requirement 7.4).
    """
    # ``cancel_flag`` is a non-blocking synchronous callable; model it as
    # a closure over a mutable counter. Polls beyond the 5 documented
    # check-points return ``False`` so an accidental extra poll would
    # surface as a failed step-count assertion rather than an IndexError.
    pattern = [False] * 5
    pattern[k - 1] = True
    poll_count = [0]

    def _cancel_flag() -> bool:
        idx = poll_count[0]
        poll_count[0] += 1
        if idx >= len(pattern):
            return False
        return pattern[idx]

    recorder = PipelineRecorder()
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=_cancel_flag,
            metric_prefix="async_task",
        )

    # ---------------- Result_Dict ----------------
    # Requirement 9.6: error on cancellation is exactly "Task cancelled".
    assert result["status"] == "cancelled", (
        f"Expected status='cancelled' at check-point k={k}, "
        f"got result={result!r}"
    )
    assert result.get("error") == "Task cancelled", (
        f"Expected error='Task cancelled' at check-point k={k}, "
        f"got result={result!r}"
    )

    # ---------------- Step call ordering ----------------
    # Requirements 5.3, 5.4: steps 1..k-1 ran in order; steps k..5 did
    # not run.
    observed_step_names = [call.name for call in recorder.step_calls]
    expected_step_names = _STEPS_BEFORE_CHECKPOINT[k]
    assert observed_step_names == expected_step_names, (
        f"At check-point k={k}, expected step prefix "
        f"{expected_step_names!r}, got {observed_step_names!r}"
    )

    # ---------------- DynamoDB transition ----------------
    # Requirements 5.6, 7.1, 7.5: terminal write is CANCELLED, exactly
    # once, following the initial RUNNING row.
    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "CANCELLED"], (
        f"At check-point k={k}, expected DDB transition RUNNING -> "
        f"CANCELLED, got {ddb_statuses!r}"
    )

    # ---------------- Metrics ----------------
    # Requirements 5.6, 7.2: exactly one ``async_task.cancelled`` counter.
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["async_task.cancelled"], (
        f"At check-point k={k}, expected exactly one "
        f"async_task.cancelled counter, got {metric_names!r}"
    )

    # Requirement 7.4: no histogram on the cancellation path.
    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"At check-point k={k}, expected no histogram events on "
        f"cancellation, got {histogram_names!r}"
    )


# ---------------------------------------------------------------------------
# DDB terminal-write failure unit tests (Task 3.5, Row 14 of the error
# classification table in ``design.md``).
#
# When the terminal ``update_job_status`` call itself raises, the pipeline
# must (per Requirement 7.6):
#
#   1. Log the DDB exception via ``logger.exception``.
#   2. Still emit the outer-case Terminal_Metric
#      (``{metric_prefix}.success`` / ``.failure`` / ``.cancelled``).
#   3. Still return the outer-case Result_Dict.
#   4. Not propagate the DDB exception to the caller (Requirement 7.7).
#
# Row 14 applies uniformly across all three outer exit paths (COMPLETE,
# FAILED, CANCELLED); one test covers each. The DDB exception is injected
# via ``PipelineRecorder(update_job_status_side_effect=...)``, which only
# raises on the terminal ``update_job_status`` call (the initial
# ``write_job_record`` call still succeeds so the pipeline reaches its
# terminal path normally).
#
# ``logger.exception`` is observed by patching
# ``container.pipeline.logger`` in-place via ``unittest.mock.patch.object``;
# this is the cleanest observation point because the pipeline module
# creates its logger with ``logging.getLogger(__name__)`` at import time.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ddb_terminal_write_failure_on_complete_path() -> None:
    """Row 14 on the COMPLETE path: terminal DDB write raises.

    **Validates: Requirements 7.6, 7.7, 14.4**

    Happy-path inputs plus
    ``update_job_status_side_effect=RuntimeError("DDB down")``. The
    pipeline reaches its success terminal path, the terminal
    ``update_job_status`` call raises, and the pipeline must:

    1. Log the DDB exception via ``logger.exception`` (not ``logger.error``
       or a re-raise).
    2. Still emit the outer-case Terminal_Metric ``code.success`` plus
       the ``code.duration`` histogram (success-path invariants are
       preserved because Requirement 7.3 pins the histogram to the
       success exit).
    3. Still return the outer-case Result_Dict with
       ``status == "complete"``.
    4. Not propagate the DDB exception to the caller.
    """
    recorder = PipelineRecorder(
        update_job_status_side_effect=RuntimeError("DDB down")
    )
    with recorder.patch(), patch.object(
        pipeline_module.logger, "exception"
    ) as mock_exc:
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    # ---------------- Result_Dict (Requirement 7.7) ----------------
    # The outer-case Result_Dict is still returned; no exception escapes.
    assert result["status"] == "complete", (
        f"Expected status='complete' despite terminal DDB write failure, "
        f"got result={result!r}"
    )

    # ---------------- Terminal_Metric (Requirement 7.6) ----------------
    # Outer-case Terminal_Metric is still emitted on the success path.
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.success"], (
        f"Expected outer-case terminal metric code.success despite DDB "
        f"write failure, got {metric_names!r}"
    )

    # Requirement 7.3: duration histogram is tied to the success exit and
    # is emitted independently of the DDB terminal write outcome.
    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == ["code.duration"], (
        f"Expected code.duration histogram on the success path despite "
        f"DDB write failure, got {histogram_names!r}"
    )

    # ---------------- logger.exception (Requirement 7.6) --------------
    assert mock_exc.called, (
        "Expected logger.exception to be invoked when the terminal DDB "
        "update_job_status call raised; it was not called."
    )


@pytest.mark.asyncio
async def test_ddb_terminal_write_failure_on_failed_path() -> None:
    """Row 14 on the FAILED path: step raises, then terminal DDB write raises.

    **Validates: Requirements 7.6, 7.7, 14.4**

    A step-level exception (``resolve_git_credential`` raising
    ``RuntimeError("x")``) drives the pipeline into the failure terminal
    path, where the terminal ``update_job_status`` call itself raises
    (``update_job_status_side_effect=RuntimeError("DDB down")``). The
    pipeline must:

    1. Log the DDB exception via ``logger.exception``.
    2. Still emit the outer-case Terminal_Metric ``code.failure`` (NOT
       ``code.success``; the outer case is the step failure).
    3. NOT emit the ``code.duration`` histogram (Requirement 7.4; the
       histogram is bound to the success exit only).
    4. Still return the outer-case Result_Dict with
       ``status == "failed"`` and ``error == "x"``.
    5. Not propagate the DDB exception to the caller.
    """
    step_exc = RuntimeError("x")
    recorder = PipelineRecorder(
        cred_side_effect=step_exc,
        update_job_status_side_effect=RuntimeError("DDB down"),
    )
    with recorder.patch(), patch.object(
        pipeline_module.logger, "exception"
    ) as mock_exc:
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    # ---------------- Result_Dict (Requirement 7.7) ----------------
    assert result["status"] == "failed", (
        f"Expected status='failed' despite terminal DDB write failure, "
        f"got result={result!r}"
    )
    assert result.get("error") == "x", (
        f"Expected error='x' (from the step exception) despite terminal "
        f"DDB write failure, got result={result!r}"
    )

    # ---------------- Terminal_Metric (Requirement 7.6) ----------------
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["code.failure"], (
        f"Expected outer-case terminal metric code.failure despite DDB "
        f"write failure, got {metric_names!r}"
    )

    # Requirement 7.4: no histogram on the failure path.
    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"Expected no histogram events on the failure path, got "
        f"{histogram_names!r}"
    )

    # ---------------- logger.exception (Requirement 7.6) --------------
    assert mock_exc.called, (
        "Expected logger.exception to be invoked when the terminal DDB "
        "update_job_status call raised; it was not called."
    )


@pytest.mark.asyncio
async def test_ddb_terminal_write_failure_on_cancelled_path() -> None:
    """Row 14 on the CANCELLED path: cancel fires, then terminal DDB write raises.

    **Validates: Requirements 7.6, 7.7, 14.4**

    ``cancel_flag`` returns ``True`` on the first poll (Check_Point 1,
    before ``resolve_git_credential``), driving the pipeline into the
    cancellation terminal path. The terminal ``update_job_status`` call
    raises (``update_job_status_side_effect=RuntimeError("DDB down")``).
    ``metric_prefix="async_task"`` mirrors the only production caller
    that passes a non-``None`` ``cancel_flag``. The pipeline must:

    1. Log the DDB exception via ``logger.exception``.
    2. Still emit the outer-case Terminal_Metric
       ``async_task.cancelled``.
    3. NOT emit the ``async_task.duration`` histogram (Requirement 7.4).
    4. Still return the outer-case Result_Dict with
       ``status == "cancelled"`` and ``error == "Task cancelled"``.
    5. Not propagate the DDB exception to the caller.
    """
    poll_count = [0]

    def _cancel_flag() -> bool:
        idx = poll_count[0]
        poll_count[0] += 1
        # True on the first poll (Check_Point 1, before
        # resolve_git_credential); False on any subsequent poll (defense
        # in depth; the pipeline should not poll again after a True).
        return idx == 0

    recorder = PipelineRecorder(
        update_job_status_side_effect=RuntimeError("DDB down")
    )
    with recorder.patch(), patch.object(
        pipeline_module.logger, "exception"
    ) as mock_exc:
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=_cancel_flag,
            metric_prefix="async_task",
        )

    # ---------------- Result_Dict (Requirement 7.7) ----------------
    assert result["status"] == "cancelled", (
        f"Expected status='cancelled' despite terminal DDB write "
        f"failure, got result={result!r}"
    )
    assert result.get("error") == "Task cancelled", (
        f"Expected error='Task cancelled' on the cancellation path, "
        f"got result={result!r}"
    )

    # ---------------- Terminal_Metric (Requirement 7.6) ----------------
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["async_task.cancelled"], (
        f"Expected outer-case terminal metric async_task.cancelled "
        f"despite DDB write failure, got {metric_names!r}"
    )

    # Requirement 7.4: no histogram on the cancellation path.
    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == [], (
        f"Expected no histogram events on the cancellation path, got "
        f"{histogram_names!r}"
    )

    # ---------------- logger.exception (Requirement 7.6) --------------
    assert mock_exc.called, (
        "Expected logger.exception to be invoked when the terminal DDB "
        "update_job_status call raised; it was not called."
    )


# ---------------------------------------------------------------------------
# ``runtime_session_id`` persistence unit test.
#
# The pipeline always writes the initial ``RUNNING`` row itself (there is
# no ``_write_initial_record=False`` escape hatch). When the Async_Tool
# passes a ``runtime_session_id`` captured from the request header, the
# pipeline must forward it to ``write_job_record`` so that ``cancel_task``
# can later fall back to ``StopRuntimeSession`` for cross-session
# cancellation.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_session_id_is_persisted_on_initial_record() -> None:
    """``runtime_session_id`` is forwarded into the initial ``RUNNING`` row.

    **Validates: Requirements 3.3, 14.4**

    Mirrors the Async_Tool's wiring: async-style callbacks
    (``on_progress=None``, ``on_oauth_needed=None``,
    ``cancel_flag=lambda: False``), ``metric_prefix="async_task"``, and
    a ``runtime_session_id`` value. The pipeline must:

    1. Call ``write_job_record`` exactly once, with
       ``status="RUNNING"`` and ``runtime_session_id="session-abc-123"``.
    2. Otherwise preserve the async-style success path invariants:
       5 step calls in documented order, DDB transition
       ``RUNNING -> COMPLETE``, one ``async_task.success`` counter, and
       one ``async_task.duration`` histogram.
    """
    recorder = PipelineRecorder()
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=_USER_ID,
            job_id=_JOB_ID,
            task_description=_TASK_DESCRIPTION,
            repo_url=_REPO_URL,
            base_branch=_BASE_BRANCH,
            target_branch=_TARGET_BRANCH,
            work_dir=_WORK_DIR,
            timeout_minutes=_TIMEOUT_MINUTES,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=lambda: False,
            metric_prefix="async_task",
            runtime_session_id="session-abc-123",
        )

    # ---------------- Result_Dict ----------------
    assert result["status"] == "complete", (
        f"Expected status='complete', got result={result!r}"
    )

    # ---------------- write_job_record called once with RUNNING +
    # runtime_session_id ----------------
    write_job_calls = [
        w for w in recorder.ddb_writes if w.kind == "write_job_record"
    ]
    assert len(write_job_calls) == 1, (
        f"Expected write_job_record to be called exactly once, got "
        f"{len(write_job_calls)}: {write_job_calls!r}"
    )
    assert write_job_calls[0].status == "RUNNING", (
        f"Expected initial write_job_record status='RUNNING', got "
        f"{write_job_calls[0].status!r}"
    )
    assert (
        write_job_calls[0].kwargs.get("runtime_session_id")
        == "session-abc-123"
    ), (
        f"Expected runtime_session_id='session-abc-123' in "
        f"write_job_record kwargs, got "
        f"{write_job_calls[0].kwargs.get('runtime_session_id')!r}"
    )

    # ---------------- DynamoDB transition ----------------
    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "COMPLETE"], (
        f"Expected DDB transition RUNNING -> COMPLETE, got "
        f"{ddb_statuses!r}"
    )

    # ---------------- Step call ordering ----------------
    step_names = [call.name for call in recorder.step_calls]
    assert step_names == _EXPECTED_STEP_ORDER, (
        f"Step functions were not invoked in the documented order: "
        f"got {step_names!r}, expected {_EXPECTED_STEP_ORDER!r}"
    )

    # ---------------- Metrics ----------------
    metric_names = [e.name for e in recorder.metric_events]
    assert metric_names == ["async_task.success"], (
        f"Expected exactly one async_task.success counter, got "
        f"{metric_names!r}"
    )

    histogram_names = [e.name for e in recorder.histogram_events]
    assert histogram_names == ["async_task.duration"], (
        f"Expected exactly one async_task.duration histogram, got "
        f"{histogram_names!r}"
    )
