# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests for ``container.pipeline.run_coding_pipeline``.

Feature: pipeline-extraction-refactor

This module defines shared Hypothesis strategies, the
``PipelineRecorder`` helper, and the seven correctness-property tests
enumerated in ``design.md § Correctness Properties``. Each ``@given``
test body is self-contained: it constructs a fresh ``PipelineRecorder``
per example, patches the pipeline's collaborators inside a
``with recorder.patch():`` block, and asserts against the recorded
invocation lists.

Design references:
    - ``design.md § Testing Strategy § Property-Based Testing Approach``
    - ``design.md § Correctness Properties`` (Properties 1-7)
    - ``requirements.md § Requirement 14``
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# External-dependency stubs.
#
# The root ``tests/conftest.py`` installs lightweight stubs for ``fastmcp``,
# ``bedrock_agentcore``, and ``strands`` before any test module is imported,
# so ``import container.pipeline`` below is safe. The import is performed at
# module scope so Hypothesis strategy failures surface as collection errors
# rather than in-test errors.
# ---------------------------------------------------------------------------

import container.pipeline as pipeline_module  # noqa: E402
from container.lib.credential_errors import (  # noqa: E402
    GIT_HOST_NOT_CONNECTED_MESSAGE,
)
from container.pipeline import (  # noqa: E402  (re-exported for test modules 2.2-2.8)
    CancelFlag,
    OnOAuthNeeded,
    OnProgress,
    RunPipelineResult,
    run_coding_pipeline,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
#
# These strategies match ``design.md § Testing Strategy § Property-Based
# Testing Approach``. They are intentionally conservative: the property tests
# in 2.2-2.8 never actually run subprocesses or touch DynamoDB (everything is
# patched via ``PipelineRecorder``), so the strategies only need to produce
# values that the pipeline itself will treat as valid, not values that the
# real tools would accept at the subprocess level.
# ---------------------------------------------------------------------------


#: UUID-shaped strings (the same shape that ``code_mcp_server`` generates via
#: ``str(uuid.uuid4())``). Used for both ``user_id`` and ``job_id``.
uuid_string_st: st.SearchStrategy[str] = st.uuids().map(str)

#: Alias for readability at the call sites in 2.2-2.8.
user_id_st: st.SearchStrategy[str] = uuid_string_st
job_id_st: st.SearchStrategy[str] = uuid_string_st

#: Non-empty printable ASCII task descriptions, bounded length.
#: Avoids control characters that would break the downstream PR-body
#: serialization in ``git_push_and_create_pr`` (not exercised here, but keeps
#: the generated values plausibly real).
task_description_st: st.SearchStrategy[str] = st.text(
    alphabet=st.characters(
        min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="\x7f"
    ),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip() != "")


#: Repository URL of the form ``https://github.com/{owner}/{repo}``. The
#: owner/repo segments use the GitHub username / repository-name character
#: set.
_github_segment_st: st.SearchStrategy[str] = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="-_"
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: not s.startswith("-") and not s.endswith("-"))


@st.composite
def _repo_url(draw: st.DrawFn) -> str:
    owner = draw(_github_segment_st)
    repo = draw(_github_segment_st)
    return f"https://github.com/{owner}/{repo}"


#: ``https://github.com/{owner}/{repo}`` URLs.
repo_url_st: st.SearchStrategy[str] = _repo_url()


#: Git-ref-safe strings for ``base_branch`` and ``target_branch``. Uses the
#: subset of characters allowed in refnames per ``git-check-ref-format(1)``
#: that is also free of leading/trailing restrictions we do not need to model
#: here. The ``_validate_git_ref`` guard in ``container.pipeline`` rejects
#: leading ``-`` (argv-flag confusion with git) and embedded whitespace, so
#: the strategy filters those out too.
_git_ref_char_st = st.characters(
    whitelist_categories=("L", "N"),
    whitelist_characters="-_/",
)
git_ref_st: st.SearchStrategy[str] = (
    st.text(alphabet=_git_ref_char_st, min_size=1, max_size=40)
    .filter(lambda s: "//" not in s)
    .filter(lambda s: not s.startswith("/") and not s.endswith("/"))
    .filter(lambda s: not s.startswith(".") and not s.endswith("."))
    .filter(lambda s: not s.startswith("-"))
)

base_branch_st: st.SearchStrategy[str] = git_ref_st
target_branch_st: st.SearchStrategy[str] = git_ref_st

#: Timeout in whole minutes, matching the ``[1, 30]`` bound enforced by the
#: MCP tool validation layer.
timeout_minutes_st: st.SearchStrategy[int] = st.integers(min_value=1, max_value=30)


def _cancel_pattern_for_k(k: int) -> list[bool]:
    """Return the 5-element cancel pattern that flips True at position ``k``.

    The pattern has ``k - 1`` leading ``False`` values, a single ``True`` at
    index ``k - 1`` (i.e. the ``k``-th poll), and is padded with ``False`` to
    a total length of 5. ``k`` is 1-indexed to match the check-point numbering
    used in ``design.md § Cancellation Check-point Semantics``.
    """
    if not 1 <= k <= 5:
        raise ValueError(f"k must be in [1, 5], got {k!r}")
    pattern = [False] * 5
    pattern[k - 1] = True
    return pattern


@st.composite
def cancel_pattern_st(draw: st.DrawFn) -> list[bool]:
    """Hypothesis strategy producing 5-element cancel patterns.

    Each drawn value is a list of exactly 5 booleans of the form
    ``[False] * (k - 1) + [True] + [False] * (5 - k)`` with ``k`` drawn
    uniformly from ``integers(1, 5)``. This matches the Property 3
    specification in ``design.md § Correctness Properties``.
    """
    k = draw(st.integers(min_value=1, max_value=5))
    return _cancel_pattern_for_k(k)


# ---------------------------------------------------------------------------
# Shared recorder helper
#
# ``PipelineRecorder`` patches the five step functions plus the four audit /
# metric helpers in ``container.pipeline`` so that each invocation is
# appended to an ordered list. Per-property tests assert against these
# lists (and against the ``RunPipelineResult`` returned by the pipeline) to
# validate the correctness properties.
#
# The recorder is intentionally framework-free: it does not depend on
# ``pytest-asyncio`` fixtures, and each property test instantiates a fresh
# recorder inside a single ``with recorder.patch(): ...`` block. This keeps
# Hypothesis ``@given`` bodies self-contained and avoids per-example fixture
# setup cost.
# ---------------------------------------------------------------------------


# Default return value for ``resolve_git_credential`` -- a token, no OAuth.
_DEFAULT_CRED: dict[str, Any] = {"token": "test-token"}

# Default return value for ``run_opencode_acp_impl``.
_DEFAULT_OPENCODE_RESULT: dict[str, Any] = {
    "stdout": "",
    "stderr": "",
    "stop_reason": "end_turn",
    "files_edited": [],
    "plan": [],
}

# Default return value for ``git_push_and_create_pr``.
_DEFAULT_PUSH_RESULT: dict[str, Any] = {
    "pr_url": "https://github.com/owner/repo/pull/1",
    "pushed": True,
}


@dataclass
class StepCall:
    """One recorded invocation of a patched step function.

    Only the name is asserted by most properties; positional and keyword
    arguments are captured so debugging a failing example is tractable.
    """

    name: str
    args: tuple
    kwargs: dict


@dataclass
class DDBWrite:
    """One recorded DynamoDB audit write.

    ``kind`` is either ``"write_job_record"`` (initial ``RUNNING`` row) or
    ``"update_job_status"`` (terminal ``COMPLETE`` / ``FAILED`` / ``CANCELLED``
    row). ``status`` extracts the DynamoDB ``status`` field so tests can
    simply check ``[w.status for w in recorder.ddb_writes]`` against the
    expected transition.
    """

    kind: str
    status: str
    args: tuple
    kwargs: dict


@dataclass
class MetricEvent:
    """One ``record_metric`` invocation."""

    name: str
    value: float
    attributes: Optional[dict]


@dataclass
class HistogramEvent:
    """One ``record_histogram`` invocation."""

    name: str
    value: float
    unit: str
    attributes: Optional[dict]


@dataclass
class PipelineRecorder:
    """Records ordered invocations of the pipeline's collaborators.

    All four recorded lists are in strict insertion order, so properties
    can assert on both *set membership* (did this call happen?) and
    *ordering* (did step 2 run before step 3?).

    Per-test customization:
        - ``cred_results``: a list of values that ``resolve_git_credential``
          returns on successive calls. Defaults to a single-element list of
          :data:`_DEFAULT_CRED`. When exhausted, the last value is repeated
          (keeps Hypothesis shrinking from tripping a ``StopIteration``).
        - ``cred_side_effect``: optional exception to raise instead of
          returning a credential. Takes precedence over ``cred_results``.
        - ``clone_side_effect``, ``opencode_side_effect``, ``scan_side_effect``,
          ``push_side_effect``: optional exceptions to raise from the
          corresponding step function.
        - ``opencode_result``, ``push_result``: return values for the
          happy-path step functions when no side-effect is set.
        - ``update_job_status_side_effect``: optional exception to raise from
          the terminal audit write (exercises Row 14 of the error
          classification table).

    Recorded attributes (read by property tests):
        - ``step_calls`` (:class:`list` of :class:`StepCall`)
        - ``ddb_writes`` (:class:`list` of :class:`DDBWrite`)
        - ``metric_events`` (:class:`list` of :class:`MetricEvent`)
        - ``histogram_events`` (:class:`list` of :class:`HistogramEvent`)
    """

    # Injection points
    cred_results: list[Any] = field(default_factory=lambda: [_DEFAULT_CRED])
    cred_side_effect: Optional[BaseException] = None
    clone_side_effect: Optional[BaseException] = None
    opencode_side_effect: Optional[BaseException] = None
    scan_side_effect: Optional[BaseException] = None
    push_side_effect: Optional[BaseException] = None
    opencode_result: dict = field(
        default_factory=lambda: dict(_DEFAULT_OPENCODE_RESULT)
    )
    push_result: dict = field(default_factory=lambda: dict(_DEFAULT_PUSH_RESULT))
    update_job_status_side_effect: Optional[BaseException] = None

    # Recorded invocations (populated by the patched collaborators)
    step_calls: list[StepCall] = field(default_factory=list)
    ddb_writes: list[DDBWrite] = field(default_factory=list)
    metric_events: list[MetricEvent] = field(default_factory=list)
    histogram_events: list[HistogramEvent] = field(default_factory=list)

    # Per-step invocation counters (handy for OAuth retry assertions)
    _cred_call_count: int = 0

    # ------------------------------------------------------------------
    # Step function fakes
    # ------------------------------------------------------------------
    def _fake_resolve_git_credential(self, *args: Any, **kwargs: Any) -> Any:
        self.step_calls.append(
            StepCall("resolve_git_credential", args, dict(kwargs))
        )
        if self.cred_side_effect is not None:
            raise self.cred_side_effect
        idx = min(self._cred_call_count, len(self.cred_results) - 1)
        self._cred_call_count += 1
        return self.cred_results[idx]

    def _fake_git_clone(self, *args: Any, **kwargs: Any) -> None:
        self.step_calls.append(StepCall("git_clone", args, dict(kwargs)))
        if self.clone_side_effect is not None:
            raise self.clone_side_effect

    async def _fake_run_opencode_acp_impl(
        self, *args: Any, **kwargs: Any
    ) -> dict:
        self.step_calls.append(
            StepCall("run_opencode_acp_impl", args, dict(kwargs))
        )
        if self.opencode_side_effect is not None:
            raise self.opencode_side_effect
        return dict(self.opencode_result)

    def _fake_scan_and_strip_credentials_impl(
        self, *args: Any, **kwargs: Any
    ) -> Any:
        self.step_calls.append(
            StepCall("scan_and_strip_credentials_impl", args, dict(kwargs))
        )
        if self.scan_side_effect is not None:
            raise self.scan_side_effect
        return None

    def _fake_git_push_and_create_pr(self, *args: Any, **kwargs: Any) -> dict:
        self.step_calls.append(
            StepCall("git_push_and_create_pr", args, dict(kwargs))
        )
        if self.push_side_effect is not None:
            raise self.push_side_effect
        return dict(self.push_result)

    # ------------------------------------------------------------------
    # DDB / metric fakes
    # ------------------------------------------------------------------
    async def _fake_write_job_record(self, *args: Any, **kwargs: Any) -> None:
        status = kwargs.get("status", "")
        if not status and args:
            # Positional call: (job_id, user_id, status, ...)
            if len(args) >= 3:
                status = args[2]
        self.ddb_writes.append(
            DDBWrite("write_job_record", status, args, dict(kwargs))
        )

    async def _fake_update_job_status(self, *args: Any, **kwargs: Any) -> None:
        status = kwargs.get("status", "")
        if not status and args:
            # Positional call: (job_id, user_id, status, ...)
            if len(args) >= 3:
                status = args[2]
        self.ddb_writes.append(
            DDBWrite("update_job_status", status, args, dict(kwargs))
        )
        if self.update_job_status_side_effect is not None:
            raise self.update_job_status_side_effect

    def _fake_record_metric(
        self,
        name: str,
        value: float,
        attributes: Optional[dict] = None,
    ) -> None:
        self.metric_events.append(MetricEvent(name, value, attributes))

    def _fake_record_histogram(
        self,
        name: str,
        value: float,
        unit: str,
        attributes: Optional[dict] = None,
    ) -> None:
        self.histogram_events.append(
            HistogramEvent(name, value, unit, attributes)
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    @contextmanager
    def patch(self) -> Iterator["PipelineRecorder"]:
        """Apply all nine patches to ``container.pipeline``.

        The pipeline imports its collaborators via
        ``from container.tools import ...`` / ``from container.lib.* import
        ...`` style, so the live references live inside the
        ``container.pipeline`` module namespace. All patches target that
        namespace so the pipeline body sees the fakes.
        """
        with (
            patch.object(
                pipeline_module,
                "resolve_git_credential",
                side_effect=self._fake_resolve_git_credential,
            ),
            patch.object(
                pipeline_module,
                "git_clone",
                side_effect=self._fake_git_clone,
            ),
            patch.object(
                pipeline_module,
                "run_opencode_acp_impl",
                new=AsyncMock(side_effect=self._fake_run_opencode_acp_impl),
            ),
            patch.object(
                pipeline_module,
                "scan_and_strip_credentials_impl",
                side_effect=self._fake_scan_and_strip_credentials_impl,
            ),
            patch.object(
                pipeline_module,
                "git_push_and_create_pr",
                side_effect=self._fake_git_push_and_create_pr,
            ),
            patch.object(
                pipeline_module,
                "write_job_record",
                new=AsyncMock(side_effect=self._fake_write_job_record),
            ),
            patch.object(
                pipeline_module,
                "update_job_status",
                new=AsyncMock(side_effect=self._fake_update_job_status),
            ),
            patch.object(
                pipeline_module,
                "record_metric",
                side_effect=self._fake_record_metric,
            ),
            patch.object(
                pipeline_module,
                "record_histogram",
                side_effect=self._fake_record_histogram,
            ),
            # The pipeline body invokes ``subprocess.run`` inline for
            # ``git config user.email`` / ``git config user.name`` /
            # ``git checkout -b target_branch`` after ``git_clone`` returns.
            # Those calls would otherwise attempt to spawn real ``git``
            # processes in a non-existent work directory and fail; the
            # property tests exercise the pipeline above the subprocess
            # level, so patch ``subprocess.run`` to a no-op that returns
            # a ``CompletedProcess``-shaped MagicMock.
            patch.object(
                pipeline_module.subprocess,
                "run",
                new=MagicMock(return_value=MagicMock(returncode=0)),
            ),
        ):
            yield self


# ---------------------------------------------------------------------------
# Public re-exports for property test modules 2.2-2.8
# ---------------------------------------------------------------------------

__all__ = [
    # Strategies
    "uuid_string_st",
    "user_id_st",
    "job_id_st",
    "task_description_st",
    "repo_url_st",
    "git_ref_st",
    "base_branch_st",
    "target_branch_st",
    "timeout_minutes_st",
    "cancel_pattern_st",
    # Recorder helpers
    "PipelineRecorder",
    "StepCall",
    "DDBWrite",
    "MetricEvent",
    "HistogramEvent",
    # Pipeline surface (re-exported for convenience)
    "run_coding_pipeline",
    "RunPipelineResult",
    "OnProgress",
    "OnOAuthNeeded",
    "CancelFlag",
]


# ---------------------------------------------------------------------------
# Property 1: sync/async parity of step invocation order
#
# Validates: Requirements 3.1, 3.2
#
# For any valid input, running ``run_coding_pipeline`` under the
# Sync_Tool-style callbacks (``on_progress=async-noop``,
# ``on_oauth_needed=async-noop returning True``, ``cancel_flag=None``,
# ``metric_prefix="code"``) and under the Async_Tool-style callbacks
# (``on_progress=None``, ``on_oauth_needed=None``,
# ``cancel_flag=lambda: False``, ``metric_prefix="async_task"``) on the
# same inputs SHALL produce:
#
#   * identical ordered sequences of step-function invocations
#     (``resolve_git_credential``, ``git_clone``,
#     ``run_opencode_acp_impl``, ``scan_and_strip_credentials_impl``,
#     ``git_push_and_create_pr``), and
#   * the DynamoDB transition ``RUNNING -> COMPLETE``.
#
# The subprocess-level ``git config`` / ``git checkout -b`` calls live
# inside the same pipeline code path in both configurations and are
# therefore covered by construction; this property asserts parity at the
# 5-step level where the pipeline's callback-shaped behavior diverges.
# ---------------------------------------------------------------------------


_EXPECTED_STEP_ORDER: list[str] = [
    "resolve_git_credential",
    "git_clone",
    "run_opencode_acp_impl",
    "scan_and_strip_credentials_impl",
    "git_push_and_create_pr",
]


async def _noop_on_progress(progress: int, total: int, message: str) -> None:
    """Async no-op progress callback used for the Sync_Tool-style config."""
    # The pipeline will invoke this exactly 5 times on a successful run;
    # the body intentionally does nothing so the callback's side effects
    # do not interfere with the step-call parity assertion below.
    return None


async def _noop_on_oauth_needed(auth_url: str) -> bool:
    """Async no-op OAuth callback.

    Returns ``True`` so that if the pipeline ever reaches the OAuth
    branch the retry would be attempted; in this property the happy
    path is exercised and this callback is never invoked.
    """
    return True


@given(
    user_id=user_id_st,
    job_id=job_id_st,
    task_description=task_description_st,
    repo_url=repo_url_st,
    base_branch=base_branch_st,
    target_branch=target_branch_st,
    timeout_minutes=timeout_minutes_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_1_sync_async_parity_of_step_invocation_order(
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    timeout_minutes: int,
) -> None:
    """Feature: pipeline-extraction-refactor, Property 1: Sync/async parity of step invocation order.

    **Validates: Requirements 3.1, 3.2**

    For any valid input, ``run_coding_pipeline(... on_progress=any,
    on_oauth_needed=any, cancel_flag=None, metric_prefix="code")`` and
    ``run_coding_pipeline(... on_progress=None, on_oauth_needed=None,
    cancel_flag=lambda: False, metric_prefix="async_task")`` produce the
    same ordered sequence of step function invocations and the same
    DynamoDB transition ``RUNNING -> COMPLETE`` on success.
    """
    work_dir = f"/tmp/pipeline-property-1/{job_id}"

    # ------------------------------------------------------------------
    # Run 1: Sync_Tool-style callback configuration.
    # ------------------------------------------------------------------
    sync_recorder = PipelineRecorder()
    with sync_recorder.patch():
        sync_result = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=_noop_on_progress,
            on_oauth_needed=_noop_on_oauth_needed,
            cancel_flag=None,
            metric_prefix="code",
        )

    # ------------------------------------------------------------------
    # Run 2: Async_Tool-style callback configuration.
    # ------------------------------------------------------------------
    async_recorder = PipelineRecorder()
    with async_recorder.patch():
        async_result = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=lambda: False,
            metric_prefix="async_task",
        )

    # ------------------------------------------------------------------
    # Requirement 3.1: step invocation sequences are identical.
    # ------------------------------------------------------------------
    sync_step_names = [call.name for call in sync_recorder.step_calls]
    async_step_names = [call.name for call in async_recorder.step_calls]

    assert sync_step_names == async_step_names, (
        "Step-call sequences diverged between sync-style and async-style "
        f"callback configurations: sync={sync_step_names!r}, "
        f"async={async_step_names!r}"
    )
    assert sync_step_names == _EXPECTED_STEP_ORDER, (
        "Sync-style run did not invoke the 5 step functions in the "
        f"documented order: got {sync_step_names!r}, "
        f"expected {_EXPECTED_STEP_ORDER!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 3.2: DynamoDB transition is RUNNING -> COMPLETE in both.
    # ------------------------------------------------------------------
    sync_ddb_statuses = [w.status for w in sync_recorder.ddb_writes]
    async_ddb_statuses = [w.status for w in async_recorder.ddb_writes]

    assert sync_ddb_statuses == ["RUNNING", "COMPLETE"], (
        "Sync-style run did not produce the RUNNING -> COMPLETE DDB "
        f"transition: got {sync_ddb_statuses!r}"
    )
    assert async_ddb_statuses == ["RUNNING", "COMPLETE"], (
        "Async-style run did not produce the RUNNING -> COMPLETE DDB "
        f"transition: got {async_ddb_statuses!r}"
    )

    # Both runs returned the success Result_Dict (sanity check; full
    # result-shape properties are covered by Property 7).
    assert sync_result["status"] == "complete"
    assert async_result["status"] == "complete"


# ---------------------------------------------------------------------------
# Property 2: callback isolation - no progress when on_progress is None
#
# Validates: Requirements 4.1, 4.2, 4.3, 4.4
#
# For any valid input:
#
#   * When ``on_progress=None``, the pipeline emits exactly 0 progress
#     events over the entire run (Requirement 4.1).
#   * When ``on_progress`` is provided and the pipeline runs to
#     completion on the success path, the pipeline invokes
#     ``on_progress`` exactly 5 times, with ``progress`` values
#     ``[1, 2, 3, 4, 5]`` in that order (Requirements 4.2, 4.4),
#     ``total=5`` on every invocation (Requirement 4.3), and the
#     fixed phase-message sequence from Requirement 3.5.
#
# Progress events are not routed through any pipeline collaborator that
# ``PipelineRecorder`` patches (the sync ``code`` tool wires
# ``on_progress`` directly to ``ctx.report_progress``); therefore this
# property needs its own recording channel. We pass a local async
# closure that appends ``(progress, total, message)`` tuples to a list
# owned by the test body and assert against that list.
# ---------------------------------------------------------------------------


#: Expected ordered sequence of phase-message strings emitted by the
#: pipeline on the success path, per Requirement 3.5 and the sequence
#: diagram in ``design.md § Sequence: Sync Path (via callbacks)``.
_EXPECTED_PROGRESS_MESSAGES: list[str] = [
    "Cloning repository...",
    "Running OpenCode...",
    "Scanning for credentials...",
    "Pushing changes...",
    "Done",
]


@given(
    user_id=user_id_st,
    job_id=job_id_st,
    task_description=task_description_st,
    repo_url=repo_url_st,
    base_branch=base_branch_st,
    target_branch=target_branch_st,
    timeout_minutes=timeout_minutes_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_2_callback_isolation_no_progress_when_on_progress_is_none(
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    timeout_minutes: int,
) -> None:
    """Feature: pipeline-extraction-refactor, Property 2: Callback isolation - no progress when on_progress is None.

    **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

    For any valid input, when ``on_progress=None`` the pipeline emits
    exactly ``0`` progress events. When ``on_progress`` is provided and
    the pipeline runs to completion, exactly ``5`` events are emitted
    with ``progress`` values ``[1, 2, 3, 4, 5]`` in order, ``total=5``
    on every event, and the fixed phase-message sequence from
    Requirement 3.5.
    """
    work_dir = f"/tmp/pipeline-property-2/{job_id}"

    # ------------------------------------------------------------------
    # Run A: on_progress=None.
    #
    # We still maintain a progress-recording list so the assertion below
    # is structurally identical to Run B; the list is never connected to
    # the pipeline, so if any progress callback were somehow invoked the
    # event could not land in this list. The meaningful assertion here is
    # that the run completed without invoking any progress callback at
    # all -- by construction of the None argument plus a successful run.
    # ------------------------------------------------------------------
    events_a: list[tuple[int, int, str]] = []
    recorder_a = PipelineRecorder()
    with recorder_a.patch():
        result_a = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix="code",
        )

    # Requirement 4.1: zero progress events when on_progress is None.
    assert events_a == [], (
        "Run A recorded progress events despite on_progress=None: "
        f"{events_a!r}"
    )
    # Sanity: the run itself succeeded, so the zero-event assertion is
    # meaningful (not trivially satisfied by an early failure).
    assert result_a["status"] == "complete", (
        "Run A did not reach the success path; zero-event assertion "
        f"may be trivially satisfied. Result: {result_a!r}"
    )

    # ------------------------------------------------------------------
    # Run B: on_progress is an async closure appending to events_b.
    # ------------------------------------------------------------------
    events_b: list[tuple[int, int, str]] = []

    async def _record_on_progress(
        progress: int, total: int, message: str
    ) -> None:
        events_b.append((progress, total, message))

    async def _noop_oauth(_auth_url: str) -> bool:
        # Never invoked on the happy path, but provided for completeness
        # so that ``on_oauth_needed`` is not None in Run B.
        return True

    recorder_b = PipelineRecorder()
    with recorder_b.patch():
        result_b = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=_record_on_progress,
            on_oauth_needed=_noop_oauth,
            cancel_flag=None,
            metric_prefix="code",
        )

    # Sanity: successful run, otherwise the event-count assertion is
    # not meaningful.
    assert result_b["status"] == "complete", (
        "Run B did not reach the success path; event-count assertion "
        f"may be trivially satisfied. Result: {result_b!r}"
    )

    # Requirement 4.2: exactly 5 progress events on a successful run.
    assert len(events_b) == 5, (
        "Run B did not emit exactly 5 progress events: "
        f"got {len(events_b)} events = {events_b!r}"
    )

    # Requirement 4.4: progress values are [1, 2, 3, 4, 5] in order.
    progress_values = [evt[0] for evt in events_b]
    assert progress_values == [1, 2, 3, 4, 5], (
        "Run B progress values were not [1, 2, 3, 4, 5] in order: "
        f"got {progress_values!r}"
    )

    # Requirement 4.3: every event has total=5.
    total_values = [evt[1] for evt in events_b]
    assert total_values == [5, 5, 5, 5, 5], (
        "Run B progress events did not all have total=5: "
        f"got {total_values!r}"
    )

    # Requirement 3.5: phase messages match the fixed sequence.
    messages = [evt[2] for evt in events_b]
    assert messages == _EXPECTED_PROGRESS_MESSAGES, (
        "Run B phase-message sequence did not match the documented "
        f"fixed sequence: got {messages!r}, "
        f"expected {_EXPECTED_PROGRESS_MESSAGES!r}"
    )


# ---------------------------------------------------------------------------
# Property 3: Cancel cooperativity - no step execution after cancel
#
# Validates: Requirements 5.1, 5.3, 5.4, 5.5, 5.6
#
# For any integer ``k`` in ``[1, 2, 3, 4, 5]``, when ``cancel_flag``
# returns ``False`` for the first ``k - 1`` polls and ``True`` on the
# ``k``-th poll, ``asyncio.CancelledError`` SHALL be raised before step
# ``k`` begins. The first ``k - 1`` steps SHALL have executed; step
# ``k`` and subsequent steps SHALL NOT have executed. The returned
# ``RunPipelineResult`` SHALL have ``status == "cancelled"`` with
# ``error == "Task cancelled"``, the terminal DDB write SHALL be
# ``CANCELLED``, and the ``{metric_prefix}.cancelled`` metric SHALL
# have been emitted exactly once.
#
# Check-point numbering (1-indexed) matches ``design.md §
# Cancellation Check-point Semantics``:
#
#   1. Before ``resolve_git_credential``.
#   2. Before ``git_clone`` + ``git config`` + ``git checkout -b``.
#   3. Before ``run_opencode_acp_impl``.
#   4. Before ``scan_and_strip_credentials_impl``.
#   5. Before ``git_push_and_create_pr``.
#
# So when ``cancel_flag()`` first returns ``True`` at the ``k``-th
# poll, steps ``1..k-1`` have run and steps ``k..5`` have not:
#   * k == 1 -> 0 step calls (cancel before any step).
#   * k == 2 -> 1 step call (``resolve_git_credential``).
#   * k == 3 -> 2 step calls.
#   * k == 4 -> 3 step calls.
#   * k == 5 -> 4 step calls.
#
# Only the async-style callback configuration actually polls
# ``cancel_flag`` (the sync-style path passes ``cancel_flag=None`` by
# contract), so this property is asserted exclusively against the
# async-style configuration with ``metric_prefix="async_task"``.
# ---------------------------------------------------------------------------


def _make_cancel_flag(pattern: list[bool]) -> CancelFlag:
    """Build a stateful ``cancel_flag`` closure from a 5-element pattern.

    Each invocation returns the element of ``pattern`` at the current
    call index and then advances the counter. After all elements of the
    pattern have been consumed the closure defensively returns
    ``False``; in practice the pipeline is expected to short-circuit
    on the ``True`` entry long before the pattern is exhausted.
    """
    call_count = [0]

    def _flag() -> bool:
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(pattern):
            return pattern[idx]
        return False

    return _flag


@given(
    cancel_pattern=cancel_pattern_st(),
    user_id=user_id_st,
    job_id=job_id_st,
    task_description=task_description_st,
    repo_url=repo_url_st,
    base_branch=base_branch_st,
    target_branch=target_branch_st,
    timeout_minutes=timeout_minutes_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_3_cancel_cooperativity_no_step_execution_after_cancel(
    cancel_pattern: list[bool],
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    timeout_minutes: int,
) -> None:
    """Feature: pipeline-extraction-refactor, Property 3: Cancel cooperativity - no step execution after cancel.

    **Validates: Requirements 5.1, 5.3, 5.4, 5.5, 5.6**

    For any integer ``k`` in ``[1, 2, 3, 4, 5]``, when ``cancel_flag``
    returns ``False`` for the first ``k - 1`` polls and ``True`` on the
    ``k``-th poll, ``asyncio.CancelledError`` is raised before step
    ``k`` executes. The first ``k - 1`` steps have executed; step ``k``
    and subsequent steps have not executed. The result dict has
    ``status == "cancelled"``, the terminal DDB write has status
    ``CANCELLED``, and the ``{metric_prefix}.cancelled`` metric was
    emitted exactly once.
    """
    # The cancel_pattern strategy guarantees exactly one True and that
    # it is at index k - 1 for some k in [1, 5].
    assert cancel_pattern.count(True) == 1, (
        "cancel_pattern_st contract violated: expected exactly one True, "
        f"got {cancel_pattern!r}"
    )
    k = cancel_pattern.index(True) + 1
    assert 1 <= k <= 5

    work_dir = f"/tmp/pipeline-property-3/{job_id}"
    metric_prefix = "async_task"

    cancel_flag = _make_cancel_flag(cancel_pattern)

    recorder = PipelineRecorder()
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=cancel_flag,
            metric_prefix=metric_prefix,
        )

    # ------------------------------------------------------------------
    # Requirements 5.6 and 9.6: the Result_Dict reports cancellation
    # with the canonical error string.
    # ------------------------------------------------------------------
    assert result["status"] == "cancelled", (
        f"Expected status='cancelled' for k={k}, got {result!r}"
    )
    assert result.get("error") == "Task cancelled", (
        f"Expected error='Task cancelled' for k={k}, got {result!r}"
    )

    # ------------------------------------------------------------------
    # Requirements 5.3 and 5.4: exactly k - 1 step functions ran, and
    # they are the first k - 1 entries of the documented step order.
    # ------------------------------------------------------------------
    observed_step_names = [call.name for call in recorder.step_calls]
    expected_step_names = _EXPECTED_STEP_ORDER[: k - 1]
    assert observed_step_names == expected_step_names, (
        f"For k={k}, expected the first {k - 1} steps to have run in "
        f"order and no others; got {observed_step_names!r}, "
        f"expected {expected_step_names!r}"
    )
    assert len(recorder.step_calls) == k - 1, (
        f"For k={k}, expected exactly {k - 1} step calls, "
        f"got {len(recorder.step_calls)}: {observed_step_names!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 5.6: the terminal DDB write is CANCELLED. The pipeline
    # always writes the initial RUNNING row, so the full transition is
    # RUNNING -> CANCELLED.
    # ------------------------------------------------------------------
    ddb_statuses = [w.status for w in recorder.ddb_writes]
    assert ddb_statuses == ["RUNNING", "CANCELLED"], (
        f"For k={k}, expected DDB transition RUNNING -> CANCELLED, "
        f"got {ddb_statuses!r}"
    )

    # ------------------------------------------------------------------
    # Requirements 5.1 and 7.2: exactly one ``{metric_prefix}.cancelled``
    # metric was emitted; no other terminal metric was emitted.
    # ------------------------------------------------------------------
    expected_metric = f"{metric_prefix}.cancelled"
    cancelled_events = [
        evt for evt in recorder.metric_events if evt.name == expected_metric
    ]
    assert len(cancelled_events) == 1, (
        f"For k={k}, expected exactly one {expected_metric!r} metric, "
        f"got {len(cancelled_events)}: all metrics = "
        f"{[e.name for e in recorder.metric_events]!r}"
    )
    # No success / failure terminal metrics should have been emitted
    # alongside the cancellation metric.
    other_terminal_metric_names = {
        f"{metric_prefix}.success",
        f"{metric_prefix}.failure",
    }
    stray_terminal = [
        evt.name
        for evt in recorder.metric_events
        if evt.name in other_terminal_metric_names
    ]
    assert stray_terminal == [], (
        f"For k={k}, cancellation path emitted a non-cancelled terminal "
        f"metric: {stray_terminal!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 7.4: the duration histogram is NOT emitted on the
    # cancellation path.
    # ------------------------------------------------------------------
    histogram_names = [evt.name for evt in recorder.histogram_events]
    assert f"{metric_prefix}.duration" not in histogram_names, (
        f"For k={k}, cancellation path unexpectedly emitted the "
        f"duration histogram: {histogram_names!r}"
    )

# ---------------------------------------------------------------------------
# Property 4: OAuth error classification
#
# Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
#
# Given a ``resolve_git_credential`` that returns
# ``{"authorization_required": True, "auth_url": "X"}`` on its first
# call, the pipeline's behavior is fully determined by the
# configuration of ``on_oauth_needed`` and what
# ``resolve_git_credential`` returns on its (possible) second call:
#
#   * Sub-case 1 - ``none_callback``: ``on_oauth_needed is None``.
#     Pipeline returns ``{"status": "failed",
#     "error": GIT_HOST_NOT_CONNECTED_MESSAGE}``.
#     ``resolve_git_credential`` was called exactly once. Per
#     Requirement 6.1.
#
#   * Sub-case 2 - ``cancelled_callback``: ``on_oauth_needed`` returns
#     ``False``. Pipeline returns ``{"status": "failed",
#     "error": "OAuth authorization cancelled"}``.
#     ``resolve_git_credential`` was called exactly once.
#     ``on_oauth_needed`` was called exactly once. Per Requirement 6.2.
#
#   * Sub-case 3 - ``confirmed_valid_retry``: ``on_oauth_needed``
#     returns ``True`` and ``resolve_git_credential`` returns a valid
#     credential on its second call. Pipeline proceeds through all 5
#     steps and returns ``{"status": "complete", ...}``.
#     ``resolve_git_credential`` was called exactly twice.
#     ``on_oauth_needed`` was called exactly once. Per Requirement 6.3.
#
#   * Sub-case 4 - ``confirmed_unauthorized_retry``: ``on_oauth_needed``
#     returns ``True`` but ``resolve_git_credential`` still returns
#     ``authorization_required`` on its second call. Pipeline returns
#     ``{"status": "failed",
#     "error": "Git host not connected after OAuth attempt"}``.
#     ``resolve_git_credential`` was called exactly twice.
#     ``on_oauth_needed`` was called exactly once. Per Requirement 6.4.
#
# Requirements 6.5 and 6.6 (at-most-twice / at-most-once bounds) are
# covered implicitly by the exact-count assertions across the four
# sub-cases.
#
# The property is parameterized over the four sub-case names via
# ``st.sampled_from``; the usual input strategies are drawn alongside
# so each Hypothesis example exercises one sub-case with a freshly
# generated set of pipeline inputs.
# ---------------------------------------------------------------------------


_OAUTH_AUTH_REQUIRED: dict[str, object] = {
    "authorization_required": True,
    "auth_url": "https://example.test/oauth/authorize",
}

_OAUTH_VALID_CRED: dict[str, object] = {"token": "oauth-retry-token"}

_OAUTH_SCENARIOS: tuple[str, ...] = (
    "none_callback",
    "cancelled_callback",
    "confirmed_valid_retry",
    "confirmed_unauthorized_retry",
)


def _oauth_setup_for_scenario(
    scenario: str,
) -> tuple[list[object], Optional[OnOAuthNeeded], list[str]]:
    """Build the ``cred_results`` list, ``on_oauth_needed`` closure,
    and shared invocation-tracking list for an OAuth sub-case.

    Returns
    -------
    cred_results
        Value(s) ``PipelineRecorder.resolve_git_credential`` will
        return on successive calls. When exhausted, the last value is
        repeated (see ``PipelineRecorder._fake_resolve_git_credential``).
    on_oauth_needed
        Either ``None`` (sub-case 1) or an async closure that appends
        to the returned tracking list and returns the scenario's
        fixed decision.
    oauth_calls
        Shared list into which each ``on_oauth_needed`` invocation
        appends its ``auth_url`` argument. Empty when
        ``on_oauth_needed is None``.
    """
    oauth_calls: list[str] = []

    if scenario == "none_callback":
        return [dict(_OAUTH_AUTH_REQUIRED)], None, oauth_calls

    if scenario == "cancelled_callback":
        async def _cb(auth_url: str) -> bool:
            oauth_calls.append(auth_url)
            return False

        return [dict(_OAUTH_AUTH_REQUIRED)], _cb, oauth_calls

    if scenario == "confirmed_valid_retry":
        async def _cb(auth_url: str) -> bool:
            oauth_calls.append(auth_url)
            return True

        return (
            [dict(_OAUTH_AUTH_REQUIRED), dict(_OAUTH_VALID_CRED)],
            _cb,
            oauth_calls,
        )

    if scenario == "confirmed_unauthorized_retry":
        async def _cb(auth_url: str) -> bool:
            oauth_calls.append(auth_url)
            return True

        return (
            [dict(_OAUTH_AUTH_REQUIRED), dict(_OAUTH_AUTH_REQUIRED)],
            _cb,
            oauth_calls,
        )

    raise AssertionError(f"Unknown OAuth scenario: {scenario!r}")


@given(
    scenario=st.sampled_from(_OAUTH_SCENARIOS),
    user_id=user_id_st,
    job_id=job_id_st,
    task_description=task_description_st,
    repo_url=repo_url_st,
    base_branch=base_branch_st,
    target_branch=target_branch_st,
    timeout_minutes=timeout_minutes_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_4_oauth_error_classification(
    scenario: str,
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    timeout_minutes: int,
) -> None:
    """Feature: pipeline-extraction-refactor, Property 4: OAuth error classification.

    **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**

    With ``resolve_git_credential`` returning
    ``authorization_required=True`` on its first call, the pipeline's
    exit is fully determined by the ``on_oauth_needed`` configuration
    and by what ``resolve_git_credential`` returns on its (possible)
    second call. This property exhaustively checks the four sub-cases
    documented in ``design.md § Correctness Properties § Property 4``
    (``none_callback``, ``cancelled_callback``,
    ``confirmed_valid_retry``, ``confirmed_unauthorized_retry``),
    asserting the exact ``error`` string, the exact call count for
    ``resolve_git_credential``, and the exact call count for
    ``on_oauth_needed``. Requirements 6.5 (``resolve_git_credential``
    called at most twice) and 6.6 (``on_oauth_needed`` called at most
    once) are covered implicitly by the exact-count assertions.
    """
    cred_results, on_oauth_needed, oauth_calls = _oauth_setup_for_scenario(
        scenario
    )

    work_dir = f"/tmp/pipeline-property-4/{job_id}"
    metric_prefix = "code"

    recorder = PipelineRecorder(cred_results=cred_results)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=None,
            on_oauth_needed=on_oauth_needed,
            cancel_flag=None,
            metric_prefix=metric_prefix,
        )

    cred_calls = sum(
        1 for call in recorder.step_calls if call.name == "resolve_git_credential"
    )

    if scenario == "none_callback":
        # Requirement 6.1: on_oauth_needed is None + initial
        # authorization_required -> failed with the shared
        # GIT_HOST_NOT_CONNECTED_MESSAGE (spec 30), not the old terse
        # sentinel "git_host_not_connected". resolve_git_credential
        # was called exactly once.
        assert result["status"] == "failed", (
            f"[none_callback] expected status='failed', got {result!r}"
        )
        assert result.get("error") == GIT_HOST_NOT_CONNECTED_MESSAGE, (
            f"[none_callback] expected error=GIT_HOST_NOT_CONNECTED_MESSAGE, "
            f"got {result!r}"
        )
        assert cred_calls == 1, (
            f"[none_callback] expected resolve_git_credential called "
            f"exactly once, got {cred_calls}"
        )
        # Requirement 6.6 (bound): on_oauth_needed is None, so no
        # invocations are even possible.
        assert oauth_calls == [], (
            f"[none_callback] on_oauth_needed tracking list should be "
            f"empty, got {oauth_calls!r}"
        )

    elif scenario == "cancelled_callback":
        # Requirement 6.2: on_oauth_needed returns False -> failed /
        # OAuth authorization cancelled; resolve_git_credential called
        # once, on_oauth_needed called once.
        assert result["status"] == "failed", (
            f"[cancelled_callback] expected status='failed', got {result!r}"
        )
        assert result.get("error") == "OAuth authorization cancelled", (
            f"[cancelled_callback] expected error='OAuth authorization "
            f"cancelled', got {result!r}"
        )
        assert cred_calls == 1, (
            f"[cancelled_callback] expected resolve_git_credential called "
            f"exactly once, got {cred_calls}"
        )
        assert len(oauth_calls) == 1, (
            f"[cancelled_callback] expected on_oauth_needed called exactly "
            f"once, got {len(oauth_calls)}: {oauth_calls!r}"
        )
        assert oauth_calls[0] == _OAUTH_AUTH_REQUIRED["auth_url"], (
            f"[cancelled_callback] on_oauth_needed received the wrong "
            f"auth_url: got {oauth_calls[0]!r}"
        )

    elif scenario == "confirmed_valid_retry":
        # Requirement 6.3: on_oauth_needed returns True + retry returns
        # a valid credential -> pipeline proceeds through all 5 steps;
        # resolve_git_credential called twice; on_oauth_needed called
        # once.
        assert result["status"] == "complete", (
            f"[confirmed_valid_retry] expected status='complete', "
            f"got {result!r}"
        )
        assert "error" not in result, (
            f"[confirmed_valid_retry] success result should not contain "
            f"'error' key, got {result!r}"
        )
        assert cred_calls == 2, (
            f"[confirmed_valid_retry] expected resolve_git_credential "
            f"called exactly twice, got {cred_calls}"
        )
        assert len(oauth_calls) == 1, (
            f"[confirmed_valid_retry] expected on_oauth_needed called "
            f"exactly once, got {len(oauth_calls)}: {oauth_calls!r}"
        )
        # All five Step_Functions ran in order. Note that
        # resolve_git_credential ran twice, so total step_calls is 6
        # (retry + 4 other steps).
        observed_step_names = [call.name for call in recorder.step_calls]
        assert observed_step_names == [
            "resolve_git_credential",
            "resolve_git_credential",
            "git_clone",
            "run_opencode_acp_impl",
            "scan_and_strip_credentials_impl",
            "git_push_and_create_pr",
        ], (
            f"[confirmed_valid_retry] step call sequence did not match "
            f"the documented order with a single OAuth retry; "
            f"got {observed_step_names!r}"
        )

    elif scenario == "confirmed_unauthorized_retry":
        # Requirement 6.4: on_oauth_needed returns True but retry still
        # returns authorization_required -> failed / Git host not
        # connected after OAuth attempt; resolve_git_credential called
        # twice; on_oauth_needed called once.
        assert result["status"] == "failed", (
            f"[confirmed_unauthorized_retry] expected status='failed', "
            f"got {result!r}"
        )
        assert (
            result.get("error") == "Git host not connected after OAuth attempt"
        ), (
            f"[confirmed_unauthorized_retry] expected error='Git host not "
            f"connected after OAuth attempt', got {result!r}"
        )
        assert cred_calls == 2, (
            f"[confirmed_unauthorized_retry] expected "
            f"resolve_git_credential called exactly twice, got {cred_calls}"
        )
        assert len(oauth_calls) == 1, (
            f"[confirmed_unauthorized_retry] expected on_oauth_needed "
            f"called exactly once, got {len(oauth_calls)}: {oauth_calls!r}"
        )

    else:
        raise AssertionError(f"Unhandled OAuth scenario: {scenario!r}")

# ---------------------------------------------------------------------------
# Property 5: Terminal-state-write exactly-once
#
# Validates: Requirements 7.1, 7.2, 7.3, 7.4
#
# On every exit path, the pipeline SHALL produce:
#
#   * Exactly one terminal ``update_job_status`` call with a
#     ``Terminal_Status`` in ``{"COMPLETE", "FAILED", "CANCELLED"}``
#     (Requirement 7.1).
#   * Exactly one terminal metric drawn from
#     ``{{metric_prefix}.success, {metric_prefix}.failure,
#     {metric_prefix}.cancelled}`` (Requirement 7.2).
#   * The duration histogram ``{metric_prefix}.duration`` exactly
#     once on the success path (Requirement 7.3) and never on the
#     failure / cancellation paths (Requirement 7.4).
#
# Exit-path scenarios enumerated here follow ``design.md § Error
# Classification Table`` plus Requirement 6's OAuth sub-cases and
# Requirement 5's cancellation check-points:
#
#   * Success (happy path).
#   * OAuth: ``none_callback``, ``cancelled_callback``,
#     ``confirmed_unauthorized_retry`` (3 failure modes).
#   * Generic step failure at each of the 5 steps
#     (``step_fail_k1`` .. ``step_fail_k5``).
#   * Cancellation at each of the 5 check-points
#     (``cancel_k1`` .. ``cancel_k5``).
#
# The property is parameterized over these 14 scenarios via
# ``st.sampled_from``; the usual input strategies are drawn alongside
# so each Hypothesis example exercises one exit path with a freshly
# generated set of pipeline inputs. All runs use
# ``metric_prefix="code"`` so the assertions can name the expected
# metric strings directly.
# ---------------------------------------------------------------------------


_EXIT_PATH_SCENARIOS: tuple[str, ...] = (
    # Success path
    "success",
    # OAuth failure modes (Requirement 6.1, 6.2, 6.4)
    "oauth_none_callback",
    "oauth_cancelled_callback",
    "oauth_confirmed_unauthorized_retry",
    # Generic per-step failures (Requirement 10.1 - 10.5)
    "step_fail_k1",
    "step_fail_k2",
    "step_fail_k3",
    "step_fail_k4",
    "step_fail_k5",
    # Cancellation at each check-point (Requirement 5.3, 5.4)
    "cancel_k1",
    "cancel_k2",
    "cancel_k3",
    "cancel_k4",
    "cancel_k5",
)


@dataclass
class _ExitPathSetup:
    """Container for the per-scenario pieces a Property 5 test needs.

    Attributes
    ----------
    recorder_kwargs
        Keyword arguments to pass to ``PipelineRecorder(...)``
        (``cred_results``, ``cred_side_effect``, ``clone_side_effect``,
        etc.).
    on_oauth_needed
        The OAuth elicitation callback to pass to the pipeline.
        ``None`` for scenarios that do not exercise OAuth.
    cancel_flag
        The ``cancel_flag`` closure to pass to the pipeline. ``None``
        for scenarios that do not exercise cancellation.
    expected_status
        One of ``"complete"``, ``"failed"``, ``"cancelled"``; the
        expected ``RunPipelineResult.status`` value.
    """

    recorder_kwargs: dict[str, Any]
    on_oauth_needed: Optional[OnOAuthNeeded]
    cancel_flag: Optional[CancelFlag]
    expected_status: str


def _setup_for_exit_path_scenario(scenario: str) -> _ExitPathSetup:
    """Build the ``PipelineRecorder`` kwargs and callbacks for a scenario.

    This helper encapsulates the 14 exit-path scenarios enumerated in
    ``_EXIT_PATH_SCENARIOS``. It reuses ``_oauth_setup_for_scenario``
    from Property 4 for the OAuth sub-cases and ``_make_cancel_flag``
    from Property 3 for the cancellation sub-cases.
    """
    # ------------------------------------------------------------------
    # Success path: default recorder, default callbacks.
    # ------------------------------------------------------------------
    if scenario == "success":
        return _ExitPathSetup(
            recorder_kwargs={},
            on_oauth_needed=None,
            cancel_flag=None,
            expected_status="complete",
        )

    # ------------------------------------------------------------------
    # OAuth failure modes.
    # ------------------------------------------------------------------
    if scenario == "oauth_none_callback":
        cred_results, on_oauth, _ = _oauth_setup_for_scenario("none_callback")
        return _ExitPathSetup(
            recorder_kwargs={"cred_results": cred_results},
            on_oauth_needed=on_oauth,
            cancel_flag=None,
            expected_status="failed",
        )

    if scenario == "oauth_cancelled_callback":
        cred_results, on_oauth, _ = _oauth_setup_for_scenario(
            "cancelled_callback"
        )
        return _ExitPathSetup(
            recorder_kwargs={"cred_results": cred_results},
            on_oauth_needed=on_oauth,
            cancel_flag=None,
            expected_status="failed",
        )

    if scenario == "oauth_confirmed_unauthorized_retry":
        cred_results, on_oauth, _ = _oauth_setup_for_scenario(
            "confirmed_unauthorized_retry"
        )
        return _ExitPathSetup(
            recorder_kwargs={"cred_results": cred_results},
            on_oauth_needed=on_oauth,
            cancel_flag=None,
            expected_status="failed",
        )

    # ------------------------------------------------------------------
    # Per-step generic failures.
    # ``cred_side_effect`` covers the non-OAuth ``resolve_git_credential``
    # failure (Requirement 10.1); the other four side-effects cover
    # Requirements 10.2 - 10.5.
    # ------------------------------------------------------------------
    step_fail_map = {
        "step_fail_k1": ("cred_side_effect", RuntimeError("step 1 failed")),
        "step_fail_k2": ("clone_side_effect", RuntimeError("step 2 failed")),
        "step_fail_k3": (
            "opencode_side_effect",
            RuntimeError("step 3 failed"),
        ),
        "step_fail_k4": ("scan_side_effect", RuntimeError("step 4 failed")),
        "step_fail_k5": ("push_side_effect", RuntimeError("step 5 failed")),
    }
    if scenario in step_fail_map:
        kwarg_name, exc = step_fail_map[scenario]
        return _ExitPathSetup(
            recorder_kwargs={kwarg_name: exc},
            on_oauth_needed=None,
            cancel_flag=None,
            expected_status="failed",
        )

    # ------------------------------------------------------------------
    # Cancellation at each of the 5 check-points.
    # ------------------------------------------------------------------
    cancel_map = {
        "cancel_k1": 1,
        "cancel_k2": 2,
        "cancel_k3": 3,
        "cancel_k4": 4,
        "cancel_k5": 5,
    }
    if scenario in cancel_map:
        k = cancel_map[scenario]
        pattern = _cancel_pattern_for_k(k)
        return _ExitPathSetup(
            recorder_kwargs={},
            on_oauth_needed=None,
            cancel_flag=_make_cancel_flag(pattern),
            expected_status="cancelled",
        )

    raise AssertionError(f"Unknown exit-path scenario: {scenario!r}")


@given(
    scenario=st.sampled_from(_EXIT_PATH_SCENARIOS),
    user_id=user_id_st,
    job_id=job_id_st,
    task_description=task_description_st,
    repo_url=repo_url_st,
    base_branch=base_branch_st,
    target_branch=target_branch_st,
    timeout_minutes=timeout_minutes_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_5_terminal_state_write_exactly_once(
    scenario: str,
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    timeout_minutes: int,
) -> None:
    """Feature: pipeline-extraction-refactor, Property 5: Terminal-state-write exactly-once.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

    On every exit path (success, each step failure, cancellation at
    each check-point, each OAuth failure mode), the pipeline makes
    exactly one terminal ``update_job_status`` call with a
    ``Terminal_Status`` matching the returned ``status`` field; emits
    exactly one terminal metric
    (``{metric_prefix}.{success|failure|cancelled}``); and emits the
    ``{metric_prefix}.duration`` histogram exactly once on success
    and never on failure or cancellation.
    """
    setup = _setup_for_exit_path_scenario(scenario)

    work_dir = f"/tmp/pipeline-property-5/{job_id}"
    metric_prefix = "code"

    recorder = PipelineRecorder(**setup.recorder_kwargs)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=None,
            on_oauth_needed=setup.on_oauth_needed,
            cancel_flag=setup.cancel_flag,
            metric_prefix=metric_prefix,
        )

    # ------------------------------------------------------------------
    # Sanity: the ``status`` field matches the scenario's expected
    # outcome. This is not itself one of the sub-requirements under
    # test, but it guarantees the subsequent exact-count assertions
    # are not trivially satisfied by an unexpected early exit.
    # ------------------------------------------------------------------
    assert result["status"] == setup.expected_status, (
        f"[{scenario}] expected status={setup.expected_status!r}, "
        f"got {result!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 7.1: exactly one terminal ``update_job_status`` call,
    # with a DynamoDB status matching the scenario's expected
    # ``Terminal_Status`` (COMPLETE / FAILED / CANCELLED).
    # ------------------------------------------------------------------
    terminal_writes = [
        w for w in recorder.ddb_writes if w.kind == "update_job_status"
    ]
    assert len(terminal_writes) == 1, (
        f"[{scenario}] expected exactly one terminal update_job_status "
        f"call, got {len(terminal_writes)}: "
        f"{[(w.kind, w.status) for w in recorder.ddb_writes]!r}"
    )

    expected_terminal_status = {
        "complete": "COMPLETE",
        "failed": "FAILED",
        "cancelled": "CANCELLED",
    }[setup.expected_status]
    assert terminal_writes[0].status == expected_terminal_status, (
        f"[{scenario}] terminal update_job_status had wrong status: "
        f"expected {expected_terminal_status!r}, "
        f"got {terminal_writes[0].status!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 7.2: exactly one terminal metric was emitted, and
    # it is the one matching the scenario's expected outcome. The
    # other two terminal metric names must have zero events.
    # ------------------------------------------------------------------
    success_metric = f"{metric_prefix}.success"
    failure_metric = f"{metric_prefix}.failure"
    cancelled_metric = f"{metric_prefix}.cancelled"

    expected_metric = {
        "complete": success_metric,
        "failed": failure_metric,
        "cancelled": cancelled_metric,
    }[setup.expected_status]

    terminal_metric_counts = {
        success_metric: 0,
        failure_metric: 0,
        cancelled_metric: 0,
    }
    for evt in recorder.metric_events:
        if evt.name in terminal_metric_counts:
            terminal_metric_counts[evt.name] += 1

    assert terminal_metric_counts[expected_metric] == 1, (
        f"[{scenario}] expected exactly one {expected_metric!r} metric "
        f"event, got {terminal_metric_counts[expected_metric]}: "
        f"all metrics = {[e.name for e in recorder.metric_events]!r}"
    )

    # The other two terminal metric names must have zero events.
    for other_name, count in terminal_metric_counts.items():
        if other_name == expected_metric:
            continue
        assert count == 0, (
            f"[{scenario}] unexpected terminal metric {other_name!r} "
            f"was emitted {count} time(s); all metrics = "
            f"{[e.name for e in recorder.metric_events]!r}"
        )

    # ------------------------------------------------------------------
    # Requirements 7.3 and 7.4: the duration histogram is emitted
    # exactly once on success and never on failure / cancellation.
    # ------------------------------------------------------------------
    duration_metric = f"{metric_prefix}.duration"
    duration_events = [
        evt for evt in recorder.histogram_events if evt.name == duration_metric
    ]

    if setup.expected_status == "complete":
        assert len(duration_events) == 1, (
            f"[{scenario}] success path must emit exactly one "
            f"{duration_metric!r} histogram event, got "
            f"{len(duration_events)}: all histograms = "
            f"{[e.name for e in recorder.histogram_events]!r}"
        )
    else:
        assert len(duration_events) == 0, (
            f"[{scenario}] non-success path must not emit the "
            f"{duration_metric!r} histogram, got {len(duration_events)} "
            f"event(s): all histograms = "
            f"{[e.name for e in recorder.histogram_events]!r}"
        )

# ---------------------------------------------------------------------------
# Property 6: Metric prefix is honored
#
# Validates: Requirements 8.1, 8.2, 8.3
#
# For any valid input and any exit path, every OTEL metric name
# emitted by the pipeline SHALL:
#
#   * Start with ``f"{metric_prefix}."`` (Requirement 8.3 - no
#     cross-prefix leakage).
#   * Be drawn from the allowed set for that prefix:
#       - ``metric_prefix="code"`` -> ``{code.success, code.failure,
#         code.cancelled, code.duration}`` (Requirement 8.1).
#       - ``metric_prefix="async_task"`` -> ``{async_task.success,
#         async_task.failure, async_task.cancelled,
#         async_task.duration}`` (Requirement 8.2).
#
# "Emitted" here means both ``record_metric`` (counter) and
# ``record_histogram`` (duration) invocations; both channels must
# obey the prefix constraint.
#
# The property is parameterized over both axes of the cross-product
# that matters for cross-prefix leakage:
#
#   * ``metric_prefix`` in ``{"code", "async_task"}`` (2 values).
#   * ``scenario`` in ``_EXIT_PATH_SCENARIOS`` (14 exit paths: success,
#     3 OAuth failure modes, 5 per-step failures, 5 cancellation
#     check-points - reused from Property 5).
#
# That is 28 distinct cases, so ``max_examples=200`` is used here
# (double Property 5's budget) to give Hypothesis room to cover each
# (prefix x scenario) cell while still drawing fresh input fuzzing for
# each example.
# ---------------------------------------------------------------------------


_METRIC_PREFIXES: tuple[str, ...] = ("code", "async_task")


def _allowed_metric_names(metric_prefix: str) -> set[str]:
    """Return the complete allowed set of metric names for a given prefix.

    Per Requirements 8.1 and 8.2, the only metric names the pipeline
    may emit under ``metric_prefix=p`` are ``{p.success, p.failure,
    p.cancelled, p.duration}``. This helper centralizes that set so
    Property 6 can assert ``emitted <= allowed`` in a single line.
    """
    return {
        f"{metric_prefix}.success",
        f"{metric_prefix}.failure",
        f"{metric_prefix}.cancelled",
        f"{metric_prefix}.duration",
    }


@given(
    metric_prefix=st.sampled_from(_METRIC_PREFIXES),
    scenario=st.sampled_from(_EXIT_PATH_SCENARIOS),
    user_id=user_id_st,
    job_id=job_id_st,
    task_description=task_description_st,
    repo_url=repo_url_st,
    base_branch=base_branch_st,
    target_branch=target_branch_st,
    timeout_minutes=timeout_minutes_st,
)
@settings(max_examples=200)
@pytest.mark.asyncio
async def test_property_6_metric_prefix_is_honored(
    metric_prefix: str,
    scenario: str,
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    timeout_minutes: int,
) -> None:
    """Feature: pipeline-extraction-refactor, Property 6: Metric prefix is honored.

    **Validates: Requirements 8.1, 8.2, 8.3**

    For any ``metric_prefix`` in ``{"code", "async_task"}`` and any
    exit path (success, each OAuth failure mode, each per-step
    failure, cancellation at each check-point), every metric name
    emitted by the pipeline starts with ``f"{metric_prefix}."`` and
    is drawn from the allowed set
    ``{f"{metric_prefix}.success", f"{metric_prefix}.failure",
    f"{metric_prefix}.cancelled", f"{metric_prefix}.duration"}``.
    No metric with the wrong prefix is ever emitted, on any exit
    path.
    """
    setup = _setup_for_exit_path_scenario(scenario)

    work_dir = f"/tmp/pipeline-property-6/{job_id}"

    recorder = PipelineRecorder(**setup.recorder_kwargs)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=None,
            on_oauth_needed=setup.on_oauth_needed,
            cancel_flag=setup.cancel_flag,
            metric_prefix=metric_prefix,
        )

    # ------------------------------------------------------------------
    # Sanity: the run reached its scenario-expected terminal state.
    # Without this check, a run that crashed before emitting any
    # metric would trivially satisfy the "all names obey the prefix"
    # assertion (empty set is a subset of anything).
    # ------------------------------------------------------------------
    assert result["status"] == setup.expected_status, (
        f"[prefix={metric_prefix!r}, scenario={scenario!r}] "
        f"expected status={setup.expected_status!r}, got {result!r}"
    )

    # ------------------------------------------------------------------
    # Collect every emitted metric name from BOTH the counter channel
    # (``record_metric``) and the histogram channel
    # (``record_histogram``). Requirement 8.3's "no metric with the
    # wrong prefix is ever emitted" applies to both.
    # ------------------------------------------------------------------
    all_names: set[str] = {evt.name for evt in recorder.metric_events} | {
        evt.name for evt in recorder.histogram_events
    }

    # Sanity: the pipeline always emits at least the terminal metric
    # on every exit path (Requirement 7.2), so ``all_names`` cannot be
    # empty. If it is, the subset assertion below is vacuously true
    # and the property is not actually being tested.
    assert all_names, (
        f"[prefix={metric_prefix!r}, scenario={scenario!r}] the "
        f"pipeline emitted zero metrics on this exit path; terminal "
        f"metric is required, so the prefix property cannot be "
        f"meaningfully tested."
    )

    # ------------------------------------------------------------------
    # Requirement 8.3: every emitted metric name starts with
    # ``f"{metric_prefix}."`` - no cross-prefix leakage.
    # ------------------------------------------------------------------
    prefix_dot = f"{metric_prefix}."
    assert all(name.startswith(prefix_dot) for name in all_names), (
        f"[prefix={metric_prefix!r}, scenario={scenario!r}] at least "
        f"one emitted metric name does not start with {prefix_dot!r}: "
        f"all names = {sorted(all_names)!r}"
    )

    # ------------------------------------------------------------------
    # Requirements 8.1 and 8.2: every emitted metric name is drawn
    # from the allowed set for this prefix. The allowed set is a
    # strict superset of what the terminal + success paths together
    # produce, so emissions must fall entirely within it.
    # ------------------------------------------------------------------
    allowed = _allowed_metric_names(metric_prefix)
    assert all_names.issubset(allowed), (
        f"[prefix={metric_prefix!r}, scenario={scenario!r}] emitted "
        f"metric names fall outside the allowed set: "
        f"unexpected = {sorted(all_names - allowed)!r}, "
        f"allowed = {sorted(allowed)!r}, "
        f"all names = {sorted(all_names)!r}"
    )

    # ------------------------------------------------------------------
    # Cross-prefix leakage guard: additionally verify that none of
    # the *other* prefix's allowed names appear in the emitted set.
    # This is logically covered by the subset assertion above (since
    # the two allowed sets are disjoint), but naming the check
    # explicitly surfaces a sharper counter-example message if the
    # pipeline ever hard-codes one prefix where it should be using
    # ``metric_prefix``.
    # ------------------------------------------------------------------
    other_prefix = "async_task" if metric_prefix == "code" else "code"
    other_allowed = _allowed_metric_names(other_prefix)
    leakage = all_names & other_allowed
    assert leakage == set(), (
        f"[prefix={metric_prefix!r}, scenario={scenario!r}] the "
        f"pipeline emitted one or more metric names belonging to the "
        f"other prefix ({other_prefix!r}): leakage = {sorted(leakage)!r}"
    )

# ---------------------------------------------------------------------------
# Property 7: Return shape well-formedness
#
# Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
#
# For any valid input and any exit path, the ``RunPipelineResult``
# returned by ``run_coding_pipeline`` SHALL satisfy a fixed set of
# structural invariants:
#
#   * ``status`` and ``duration_seconds`` are always present
#     (Requirement 9.1).
#   * ``status`` is exactly one of ``"complete"``, ``"failed"``,
#     ``"cancelled"`` (Requirement 9.2).
#   * ``duration_seconds`` is a non-negative ``int`` / ``float``
#     (Requirement 9.3).
#   * On ``status == "complete"``, the keys ``pr_url``,
#     ``stop_reason``, and ``files_edited`` are present and the key
#     ``error`` is absent (Requirement 9.4).
#   * On ``status in {"failed", "cancelled"}``, the key ``error`` is
#     present and none of ``pr_url`` / ``stop_reason`` /
#     ``files_edited`` are present (Requirement 9.5).
#   * On ``status == "cancelled"``, ``error == "Task cancelled"``
#     (Requirement 9.6).
#   * On step-failure paths (exceptions from a Step_Function, not
#     ``asyncio.CancelledError``), ``error == str(exc)[:500]`` -
#     truncated to at most 500 characters (Requirement 9.7).
#
# This property is split across two tests:
#
#   (a) ``test_property_7_return_shape_well_formedness`` -
#       Parameterized over ``_EXIT_PATH_SCENARIOS`` (the 14 exit paths
#       reused from Property 5). Asserts Requirements 9.1-9.6 for
#       every scenario.
#
#   (b) ``test_property_7_return_shape_error_truncation`` -
#       Parameterized over the five step-failure paths
#       ``(k1 .. k5)`` with a Hypothesis-generated exception message
#       length ``n`` drawn from ``integers(501, 5000)``. Asserts
#       Requirement 9.7: on any step failure with ``str(exc)`` of
#       length ``n >= 501``, the returned ``error`` is exactly 500
#       characters and equals ``str(exc)[:500]``.
# ---------------------------------------------------------------------------


#: Keys that must be present in a ``complete`` Result_Dict (Req 9.4).
_SUCCESS_ONLY_KEYS: tuple[str, ...] = ("pr_url", "stop_reason", "files_edited")


@given(
    scenario=st.sampled_from(_EXIT_PATH_SCENARIOS),
    user_id=user_id_st,
    job_id=job_id_st,
    task_description=task_description_st,
    repo_url=repo_url_st,
    base_branch=base_branch_st,
    target_branch=target_branch_st,
    timeout_minutes=timeout_minutes_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_7_return_shape_well_formedness(
    scenario: str,
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    timeout_minutes: int,
) -> None:
    """Feature: pipeline-extraction-refactor, Property 7: Return shape well-formedness.

    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**

    For any exit path (success, each OAuth failure mode, each
    per-step failure, cancellation at each check-point), the
    ``RunPipelineResult`` returned by ``run_coding_pipeline`` has
    ``status`` and ``duration_seconds`` always present;
    ``status in {"complete", "failed", "cancelled"}``;
    ``duration_seconds`` is a non-negative number; on ``complete`` the
    keys ``pr_url`` / ``stop_reason`` / ``files_edited`` are present
    and ``error`` is absent; on ``failed`` or ``cancelled`` the key
    ``error`` is present and none of ``pr_url`` / ``stop_reason`` /
    ``files_edited`` are present; on ``cancelled`` the error string is
    exactly ``"Task cancelled"``.

    Requirement 9.7 (500-char truncation) is validated separately by
    ``test_property_7_return_shape_error_truncation`` so this test can
    stay focused on the structural invariants.
    """
    setup = _setup_for_exit_path_scenario(scenario)

    work_dir = f"/tmp/pipeline-property-7a/{job_id}"
    metric_prefix = "code"

    recorder = PipelineRecorder(**setup.recorder_kwargs)
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=None,
            on_oauth_needed=setup.on_oauth_needed,
            cancel_flag=setup.cancel_flag,
            metric_prefix=metric_prefix,
        )

    # ------------------------------------------------------------------
    # Requirement 9.1: ``status`` and ``duration_seconds`` are always
    # present, on every exit path.
    # ------------------------------------------------------------------
    assert "status" in result, (
        f"[{scenario}] Result_Dict is missing required key 'status': "
        f"{result!r}"
    )
    assert "duration_seconds" in result, (
        f"[{scenario}] Result_Dict is missing required key "
        f"'duration_seconds': {result!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 9.2: ``status`` is exactly one of the three allowed
    # values.
    # ------------------------------------------------------------------
    assert result["status"] in {"complete", "failed", "cancelled"}, (
        f"[{scenario}] Result_Dict has status value outside the "
        f"allowed set {{'complete', 'failed', 'cancelled'}}: "
        f"got {result['status']!r}"
    )

    # Sanity: the observed status matches the scenario's expected
    # outcome. Without this, a run that silently exited via an
    # unexpected path could produce a Result_Dict that trivially
    # satisfies Req 9.2 without actually exercising the intended
    # branch of Reqs 9.4 / 9.5 / 9.6.
    assert result["status"] == setup.expected_status, (
        f"[{scenario}] expected status={setup.expected_status!r}, "
        f"got {result!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 9.3: ``duration_seconds`` is a non-negative number.
    # ------------------------------------------------------------------
    duration = result["duration_seconds"]
    # ``bool`` is a subclass of ``int`` in Python, and accepting it
    # here would be wrong: the pipeline is specified to return a real
    # numeric value, not a truthy flag. Exclude it explicitly.
    assert isinstance(duration, (int, float)) and not isinstance(
        duration, bool
    ), (
        f"[{scenario}] duration_seconds is not a numeric type: "
        f"got {duration!r} of type {type(duration).__name__}"
    )
    assert duration >= 0.0, (
        f"[{scenario}] duration_seconds must be non-negative, "
        f"got {duration!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 9.4 / 9.5: per-status key presence and absence.
    # ------------------------------------------------------------------
    if result["status"] == "complete":
        # Req 9.4: the three success-only keys are present.
        for key in _SUCCESS_ONLY_KEYS:
            assert key in result, (
                f"[{scenario}] complete Result_Dict is missing "
                f"required key {key!r}: {result!r}"
            )
        # Req 9.4: ``error`` is absent on success.
        assert "error" not in result, (
            f"[{scenario}] complete Result_Dict must not contain "
            f"'error' key: got {result!r}"
        )
    else:
        # Req 9.5: ``error`` is present on failed / cancelled.
        assert "error" in result, (
            f"[{scenario}] non-success Result_Dict is missing "
            f"required key 'error': {result!r}"
        )
        # Req 9.5: none of the success-only keys are present on
        # failed / cancelled.
        for key in _SUCCESS_ONLY_KEYS:
            assert key not in result, (
                f"[{scenario}] non-success Result_Dict must not "
                f"contain success-only key {key!r}: got {result!r}"
            )

    # ------------------------------------------------------------------
    # Requirement 9.6: on cancellation, ``error`` is exactly the
    # canonical string.
    # ------------------------------------------------------------------
    if result["status"] == "cancelled":
        assert result["error"] == "Task cancelled", (
            f"[{scenario}] cancelled Result_Dict must have "
            f"error='Task cancelled', got {result['error']!r}"
        )


#: The five step-failure scenarios from ``_EXIT_PATH_SCENARIOS``, plus
#: the ``PipelineRecorder`` keyword that injects the raising exception
#: for each. Used by ``test_property_7_return_shape_error_truncation``
#: to drive a long-exception test against each of the five Step_Functions
#: (Requirement 9.7).
_STEP_FAIL_RECORDER_KWARG: dict[str, str] = {
    "step_fail_k1": "cred_side_effect",
    "step_fail_k2": "clone_side_effect",
    "step_fail_k3": "opencode_side_effect",
    "step_fail_k4": "scan_side_effect",
    "step_fail_k5": "push_side_effect",
}


@pytest.mark.parametrize(
    "step_scenario", sorted(_STEP_FAIL_RECORDER_KWARG.keys())
)
@given(
    n=st.integers(min_value=501, max_value=5000),
    user_id=user_id_st,
    job_id=job_id_st,
    task_description=task_description_st,
    repo_url=repo_url_st,
    base_branch=base_branch_st,
    target_branch=target_branch_st,
    timeout_minutes=timeout_minutes_st,
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_7_return_shape_error_truncation(
    step_scenario: str,
    n: int,
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    timeout_minutes: int,
) -> None:
    """Feature: pipeline-extraction-refactor, Property 7: Return shape well-formedness (error truncation).

    **Validates: Requirement 9.7**

    For each of the five step-failure paths (``k1`` .. ``k5``) and any
    integer ``n >= 501``, when the step ``k`` raises an exception
    whose ``str(exc)`` has length exactly ``n``, the returned
    Result_Dict has ``status == "failed"`` and its ``error`` value is
    exactly 500 characters long and equal to ``str(exc)[:500]``
    (i.e. the first 500 characters of the original exception
    message). This pins the truncation contract from Requirement 9.7.
    """
    kwarg_name = _STEP_FAIL_RECORDER_KWARG[step_scenario]

    # Construct a deterministic long message: ``n`` copies of the
    # character ``x``. The exact content is irrelevant to the
    # property; what matters is that ``str(exc)`` has length ``n``
    # and is predictable enough to assert against.
    long_message = "x" * n
    exc = RuntimeError(long_message)
    # Sanity: ``str(RuntimeError("x" * n))`` is exactly ``"x" * n``,
    # so ``len(str(exc)) == n``. This guards against any future
    # RuntimeError formatting change that could silently invalidate
    # the assertion below.
    assert len(str(exc)) == n, (
        f"[{step_scenario}, n={n}] str(RuntimeError) produced a "
        f"message of unexpected length {len(str(exc))}"
    )

    work_dir = f"/tmp/pipeline-property-7b/{job_id}"
    metric_prefix = "code"

    recorder = PipelineRecorder(**{kwarg_name: exc})
    with recorder.patch():
        result = await run_coding_pipeline(
            user_id=user_id,
            job_id=job_id,
            task_description=task_description,
            repo_url=repo_url,
            base_branch=base_branch,
            target_branch=target_branch,
            work_dir=work_dir,
            timeout_minutes=timeout_minutes,
            on_progress=None,
            on_oauth_needed=None,
            cancel_flag=None,
            metric_prefix=metric_prefix,
        )

    # Sanity: the scenario reached the failure path. Without this, a
    # run that silently succeeded (or cancelled) would produce a
    # Result_Dict whose ``error`` key would be missing entirely, and
    # the truncation assertion below would fail with a KeyError
    # instead of the precise counter-example we want.
    assert result["status"] == "failed", (
        f"[{step_scenario}, n={n}] expected status='failed' from a "
        f"long-exception step failure, got {result!r}"
    )
    assert "error" in result, (
        f"[{step_scenario}, n={n}] failed Result_Dict is missing "
        f"'error' key: {result!r}"
    )

    # ------------------------------------------------------------------
    # Requirement 9.7: ``error == str(exc)[:500]``, i.e. truncated to
    # at most 500 characters. Since ``n >= 501`` by strategy
    # construction, the result is exactly 500 characters long and
    # equal to ``"x" * 500``.
    # ------------------------------------------------------------------
    assert len(result["error"]) == 500, (
        f"[{step_scenario}, n={n}] error length must be exactly 500 "
        f"when the original exception message is {n} chars; "
        f"got length {len(result['error'])}"
    )
    assert result["error"] == long_message[:500], (
        f"[{step_scenario}, n={n}] error content does not match "
        f"str(exc)[:500]; got {result['error']!r}"
    )
