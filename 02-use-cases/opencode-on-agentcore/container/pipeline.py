# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""MCP-agnostic coding pipeline.

Single source of truth for the 5-step coding pipeline
(`resolve_git_credential` -> `git_clone` -> `run_opencode_acp_impl` ->
`scan_and_strip_credentials_impl` -> `git_push_and_create_pr`) plus the
surrounding DynamoDB bookkeeping, OpenTelemetry metrics, OAuth retry, and
cooperative cancellation.

The ``run_coding_pipeline`` entry point is MCP-agnostic: all MCP primitives
(progress reporting, OAuth elicitation, cancellation signals) are injected
via optional async callback arguments. The two MCP tool handlers become
thin glue that wires FastMCP's ``ctx`` into those callback slots.

``run_coding_pipeline`` is a plain async coroutine. It is deliberately
undecorated: the function is always awaited directly (never dispatched
through a ``strands.Agent``), so there is no ``@strands.tool`` wrapper
and no agent-input schema is built.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Literal, NotRequired, Optional, TypedDict

from container.tools import (
    resolve_git_credential,
    git_clone,
    run_opencode_acp_impl,
    scan_and_strip_credentials_impl,
    git_push_and_create_pr,
)
from container.lib.dynamodb_helpers import write_job_record, update_job_status
from container.lib.metrics import record_metric, record_histogram
from container.lib.credential_errors import GIT_HOST_NOT_CONNECTED_MESSAGE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class RunPipelineResult(TypedDict):
    """Return shape of :func:`run_coding_pipeline`.

    See ``design.md`` section "Data Models" for the full contract.
    """

    status: Literal["complete", "failed", "cancelled"]
    duration_seconds: float
    # Present on success only:
    pr_url: NotRequired[str]
    stop_reason: NotRequired[str]
    files_edited: NotRequired[list[str]]
    # Present on failure or cancellation only:
    error: NotRequired[str]


# ---------------------------------------------------------------------------
# Callback type aliases
# ---------------------------------------------------------------------------

# Invoked with (progress, total, message). ``total`` is always 5. ``progress``
# is 1..5.
OnProgress = Callable[[int, int, str], Awaitable[None]]

# Invoked with (auth_url). Returns True if the user confirmed OAuth, False if
# the user cancelled elicitation.
OnOAuthNeeded = Callable[[str], Awaitable[bool]]

# Invoked with no args. Returns True if cancellation has been requested.
CancelFlag = Callable[[], bool]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_cancel(cancel_flag: Optional[CancelFlag]) -> None:
    """Poll ``cancel_flag`` and raise ``asyncio.CancelledError`` if set.

    When ``cancel_flag is None`` (the sync ``code`` tool path), no poll is
    performed. See design.md § Cancellation Check-point Semantics.
    """
    if cancel_flag is not None and cancel_flag():
        raise asyncio.CancelledError()


async def _emit_progress(
    on_progress: Optional[OnProgress],
    progress: int,
    total: int,
    message: str,
) -> None:
    """Invoke ``on_progress`` if non-``None``; otherwise no-op."""
    if on_progress is not None:
        await on_progress(progress, total, message)


def _now_iso() -> str:
    """ISO-8601 UTC timestamp matching the existing audit-record format."""
    return datetime.now(timezone.utc).isoformat()


# Schemes we accept for ``repo_url``. ``https://`` is the pipeline's
# only tested path; ``git@`` SSH is included because the clone helper
# forwards it to git directly, but see the hardening note in
# ``docs/HARDENING.md`` about egress filtering.
_ALLOWED_REPO_SCHEMES = ("https://", "git@")

# Characters that must never appear in a ``repo_url`` or a git ref,
# even though ``subprocess.run`` uses list-form argv. Blocking them
# early produces a clearer error than letting git reject the URL.
_URL_FORBIDDEN_CHARS = ("\x00", "\n", "\r", " ", "\t")


def _validate_repo_url(repo_url: str) -> None:
    """Reject malformed or suspicious ``repo_url`` values.

    The clone helper invokes git via ``subprocess.run`` with list-form
    argv, so there is no shell-injection surface; this validator's
    purpose is to fail fast on obviously malformed input (empty
    string, embedded control characters, unsupported scheme) rather
    than surfacing a cryptic git error five frames deeper. See PCSR
    triage (Rule 11) for context.
    """
    if not isinstance(repo_url, str) or not repo_url:
        raise ValueError("repo_url must be a non-empty string")
    if len(repo_url) > 2048:
        raise ValueError(f"repo_url too long ({len(repo_url)} chars, max 2048)")
    for bad in _URL_FORBIDDEN_CHARS:
        if bad in repo_url:
            raise ValueError(
                f"repo_url contains forbidden character {bad!r}"
            )
    if not repo_url.startswith(_ALLOWED_REPO_SCHEMES):
        raise ValueError(
            f"repo_url must start with one of {_ALLOWED_REPO_SCHEMES}; "
            f"got {repo_url[:64]!r}"
        )


def _validate_git_ref(ref: str, label: str) -> None:
    """Reject empty or obviously malformed git refs (branch names).

    Git itself enforces strict rules on ref names, but we reject the
    common pathological shapes up-front so the caller gets a clearer
    error: empty, whitespace, leading ``-`` (which git can confuse
    for a CLI flag), or embedded control characters.
    """
    if not isinstance(ref, str) or not ref:
        raise ValueError(f"{label} must be a non-empty string")
    if len(ref) > 255:
        raise ValueError(f"{label} too long ({len(ref)} chars, max 255)")
    if ref.startswith("-"):
        raise ValueError(f"{label} must not start with '-'; got {ref!r}")
    for bad in _URL_FORBIDDEN_CHARS:
        if bad in ref:
            raise ValueError(
                f"{label} contains forbidden character {bad!r}"
            )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_coding_pipeline(
    *,
    user_id: str,
    job_id: str,
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str,
    work_dir: str,
    timeout_minutes: int,
    metric_prefix: str,
    runtime_session_id: str = "",
    on_progress: Optional[OnProgress] = None,
    on_oauth_needed: Optional[OnOAuthNeeded] = None,
    cancel_flag: Optional[CancelFlag] = None,
) -> RunPipelineResult:
    """Run the 5-step coding pipeline.

    The pipeline always writes its own initial ``RUNNING`` row so it owns
    the full ``RUNNING -> {COMPLETE|FAILED|CANCELLED}`` transition. Callers
    that need to persist extra fields on the initial row (e.g. the async
    tool's ``runtime_session_id``) pass them through this function's
    parameters, not via a separate pre-write.

    Parameters
    ----------
    metric_prefix:
        Required namespace for every OTEL metric this invocation emits
        (``{metric_prefix}.success`` / ``.failure`` / ``.cancelled`` /
        ``.duration``). The sync ``code`` tool passes ``"code"``; the async
        ``run_coding_task`` tool passes ``"async_task"``.
    runtime_session_id:
        AgentCore runtime session id captured from the incoming request
        header. Persisted into the initial ``RUNNING`` DynamoDB row so
        ``cancel_task`` can fall back to ``StopRuntimeSession``. Empty
        string when the caller has no session id to attribute.

    See ``design.md`` section "Algorithmic Pseudocode" for the full spec.
    """
    _validate_repo_url(repo_url)
    _validate_git_ref(base_branch, "base_branch")
    if target_branch:
        _validate_git_ref(target_branch, "target_branch")

    start_time = time.time()

    await write_job_record(
        job_id=job_id,
        user_id=user_id,
        status="RUNNING",
        task_description=task_description,
        repo_url=repo_url,
        base_branch=base_branch,
        target_branch=target_branch,
        runtime_session_id=runtime_session_id,
    )

    try:
        # -- Check-point 1: before credential resolution -------------------
        _check_cancel(cancel_flag)

        cred = await asyncio.to_thread(
            resolve_git_credential, user_id=user_id, repo_url=repo_url
        )

        if cred.get("authorization_required"):
            if on_oauth_needed is None:
                raise RuntimeError(GIT_HOST_NOT_CONNECTED_MESSAGE)

            confirmed = await on_oauth_needed(cred.get("auth_url", ""))
            if not confirmed:
                raise RuntimeError("OAuth authorization cancelled")

            # Retry exactly once; no further retries after this.
            cred = await asyncio.to_thread(
                resolve_git_credential, user_id=user_id, repo_url=repo_url
            )
            if cred.get("authorization_required"):
                raise RuntimeError("Git host not connected after OAuth attempt")

        git_token = cred["token"]

        # -- Check-point 2: before clone + config + checkout ---------------
        _check_cancel(cancel_flag)
        await _emit_progress(on_progress, 1, 5, "Cloning repository...")

        await asyncio.to_thread(
            git_clone,
            repo_url=repo_url,
            token=git_token,
            base_branch=base_branch,
            work_dir=work_dir,
        )
        await asyncio.to_thread(
            subprocess.run,
            ["git", "config", "user.email", "opencode@agentcore.aws"],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )
        await asyncio.to_thread(
            subprocess.run,
            ["git", "config", "user.name", "OpenCode"],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )
        await asyncio.to_thread(
            subprocess.run,
            ["git", "checkout", "-b", target_branch],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )

        # -- Check-point 3: before OpenCode --------------------------------
        _check_cancel(cancel_flag)
        await _emit_progress(on_progress, 2, 5, "Running OpenCode...")

        oc_result = await run_opencode_acp_impl(
            work_dir=work_dir,
            task_description=task_description,
            timeout_seconds=timeout_minutes * 60,
        )

        # -- Check-point 4: before credential scan -------------------------
        _check_cancel(cancel_flag)
        await _emit_progress(on_progress, 3, 5, "Scanning for credentials...")

        scan_and_strip_credentials_impl(work_dir=work_dir, job_id=job_id)

        # -- Check-point 5: before push + PR -------------------------------
        _check_cancel(cancel_flag)
        await _emit_progress(on_progress, 4, 5, "Pushing changes...")

        push_result = await asyncio.to_thread(
            git_push_and_create_pr,
            work_dir=work_dir,
            token=git_token,
            repo_url=repo_url,
            target_branch=target_branch,
            base_branch=base_branch,
            task_description=task_description,
            job_id=job_id,
        )

        # -- Terminal success path ----------------------------------------
        duration = time.time() - start_time
        pr_url = push_result.get("pr_url") or ""
        stop_reason = oc_result.get("stop_reason", "")
        files_edited = oc_result.get("files_edited", [])

        try:
            await update_job_status(
                job_id=job_id,
                user_id=user_id,
                status="COMPLETE",
                pr_url=pr_url,
                stop_reason=stop_reason,
                files_edited=files_edited,
                duration_seconds=round(duration, 2),
                completed_at=_now_iso(),
            )
        except Exception:
            logger.exception(
                "Failed to write COMPLETE audit record for job %s", job_id
            )

        record_metric(f"{metric_prefix}.success", 1.0)
        record_histogram(f"{metric_prefix}.duration", duration, "seconds")

        await _emit_progress(on_progress, 5, 5, "Done")

        return {
            "status": "complete",
            "pr_url": pr_url,
            "stop_reason": stop_reason,
            "files_edited": files_edited,
            "duration_seconds": round(duration, 2),
        }

    except asyncio.CancelledError:
        duration = time.time() - start_time
        try:
            await update_job_status(
                job_id=job_id,
                user_id=user_id,
                status="CANCELLED",
                error="Task cancelled",
                duration_seconds=round(duration, 2),
                completed_at=_now_iso(),
            )
        except Exception:
            logger.exception(
                "Failed to write CANCELLED audit record for job %s", job_id
            )

        record_metric(f"{metric_prefix}.cancelled", 1.0)

        return {
            "status": "cancelled",
            "error": "Task cancelled",
            "duration_seconds": round(duration, 2),
        }

    except Exception as exc:
        duration = time.time() - start_time
        error_msg = str(exc)[:500]
        logger.exception("Pipeline failed for job %s", job_id)
        try:
            await update_job_status(
                job_id=job_id,
                user_id=user_id,
                status="FAILED",
                error=error_msg,
                duration_seconds=round(duration, 2),
                completed_at=_now_iso(),
            )
        except Exception:
            logger.exception(
                "Failed to write FAILED audit record for job %s", job_id
            )

        record_metric(f"{metric_prefix}.failure", 1.0)

        return {
            "status": "failed",
            "error": error_msg,
            "duration_seconds": round(duration, 2),
        }
