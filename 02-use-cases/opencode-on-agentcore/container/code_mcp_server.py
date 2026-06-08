# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode MCP Server — single FastMCP server on port 8000.

Exposes 6 OpenCode tools via Streamable HTTP:
  - code             (sync — streams progress, supports ctx.elicit() for OAuth)
  - run_coding_task   (async — returns job_id immediately, runs pipeline in background)
  - connect_git_host  (interactive — OAuth consent flow via ctx.elicit())
  - get_task_status   (query — read job record from DynamoDB)
  - list_tasks        (query — list user's jobs from DynamoDB)
  - cancel_task       (control — cancel running task, in-process first then cross-session)

Requirements: 1.1-1.6, 2.1-2.7, 3.1-3.4, 4.1-4.6, 5.1-5.3,
              6.1-6.4, 8.1-8.5, 15.1, 15.2, 16.1,
              17.1-17.4, 22.1-22.4
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

# Configure structured JSON logging to stdout so CloudWatch Logs Insights
# can filter on specific fields like job_id, user_id, and status.
from pythonjsonlogger import json as jsonlogger

_handler = logging.StreamHandler(sys.stdout)
_formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
)
_handler.setFormatter(_formatter)
logging.root.handlers = [_handler]
logging.root.setLevel(logging.INFO)
logger = logging.getLogger(__name__)

_startup_start = time.time()
logger.info("Module loading started")

from fastmcp import Context, FastMCP

logger.info("fastmcp imported (%.1fs)", time.time() - _startup_start)

from bedrock_agentcore.runtime import BedrockAgentCoreApp

logger.info("bedrock_agentcore imported (%.1fs)", time.time() - _startup_start)

from container.lib.dynamodb_helpers import (
    query_job_record,
    query_user_jobs,
    update_job_status,
)

logger.info("dynamodb_helpers imported (%.1fs)", time.time() - _startup_start)

from container.pipeline import run_coding_pipeline

logger.info("container.pipeline imported (%.1fs)", time.time() - _startup_start)

from container.lib.credential_errors import GIT_HOST_NOT_CONNECTED_MESSAGE

# ---------------------------------------------------------------------------
# FastMCP + AgentCore app
# ---------------------------------------------------------------------------
mcp = FastMCP("opencode")
app = BedrockAgentCoreApp()
logger.info("FastMCP + AgentCoreApp created (%.1fs)", time.time() - _startup_start)


# /ping health check on port 8000 — required by the AgentCore platform.
# BedrockAgentCoreApp manages Healthy/HealthyBusy via add_async_task.
@mcp.custom_route("/ping", methods=["GET"])
async def ping(request):
    from starlette.responses import JSONResponse

    status = app.get_current_ping_status()
    return JSONResponse({"status": status.value})

# In-process task registry for cancellation signaling (Req 7.1)
_running_tasks: dict[str, asyncio.Task] = {}
_cancel_flags: dict[str, bool] = {}

# ── Environment variables for control tools ───────────────────────────────
WORKLOAD_NAME = os.environ.get("WORKLOAD_NAME", "opencode_runtime")
ELICITATION_TIMEOUT_S = int(os.environ.get("ELICITATION_TIMEOUT_S", "300"))
REGION = os.environ.get("AWS_REGION", "us-east-1")

# ── Elicitation timeout helper ─────────────────────────────────────────────

async def _elicit_with_timeout(ctx, *, message, schema):
    """Wrap ctx.elicit with the configured timeout.

    Returns None on timeout OR on any elicitation failure (e.g., FastMCP version
    mismatch raising TypeError, unsupported elicitation raising AttributeError,
    transport failures raising ConnectionError). Callers already handle None
    correctly (treated as cancellation / fallback to structured error).
    """
    try:
        return await asyncio.wait_for(
            ctx.elicit(message=message, schema=schema),
            timeout=ELICITATION_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("Elicitation timed out after %ds", ELICITATION_TIMEOUT_S)
        return None
    except Exception:
        logger.warning(
            "_elicit_with_timeout: elicitation failed", exc_info=True
        )
        return None


# ── Identity SDK helpers ──────────────────────────────────────────────────

_identity_sdk_client = None


def _identity_client():
    global _identity_sdk_client
    if _identity_sdk_client is None:
        import boto3
        _identity_sdk_client = boto3.client("bedrock-agentcore", region_name=REGION)
    return _identity_sdk_client


def _get_workload_token(user_id: str) -> str:
    """Obtain a workload access token for the given user from AgentCore Identity."""
    return _identity_client().get_workload_access_token_for_user_id(
        workloadName=WORKLOAD_NAME, userId=user_id
    )["workloadAccessToken"]


def _get_oauth_callback_url() -> str:
    """Return the OAuth callback URL from environment."""
    return os.environ.get("OAUTH_CALLBACK_URL", "")


def _provider_name(domain: str) -> str:
    """Map a git host domain to its AgentCore Identity credential provider name."""
    return "github-provider" if domain == "github.com" else f"custom-{domain}"


def _get_credential(user_id: str, git_host: str):
    """Return (token, None) or (None, auth_url)."""
    token = _get_workload_token(user_id)
    params = {
        "workloadIdentityToken": token,
        "resourceCredentialProviderName": _provider_name(git_host),
        "oauth2Flow": "USER_FEDERATION",
        "scopes": ["repo"],
    }
    callback = _get_oauth_callback_url()
    if callback:
        params["resourceOauth2ReturnUrl"] = callback
        params["customState"] = json.dumps({"user_id": user_id})

    try:
        resp = _identity_client().get_resource_oauth2_token(**params)
        if resp.get("authorizationUrl"):
            return None, resp["authorizationUrl"]
        return resp["accessToken"], None
    except Exception as exc:
        # Older SDK versions raise an exception instead of returning
        # authorizationUrl in the response body. The exception class name
        # varies across SDK versions, so match by attribute or string.
        auth_url = getattr(exc, "authorization_url", None)
        if auth_url:
            return None, auth_url
        err_str = str(exc)
        if "authorizationUrl" in err_str or "AuthorizationUrl" in err_str:
            # Try to extract from the response metadata
            resp_meta = getattr(exc, "response", {})
            auth_url = resp_meta.get("authorizationUrl", "")
            if auth_url:
                return None, auth_url
        raise


# ── Response helpers ──────────────────────────────────────────────────────

def _ok(status: str, git_host: str, message: str):
    return {"status": status, "git_host": git_host, "message": message}


def _fail(git_host: str, error: str):
    return {"status": "failed", "git_host": git_host, "message": error, "error": error}


# Managed session storage base path (Req 16.1)
SESSION_STORAGE_PATH = os.environ.get(
    "SESSION_STORAGE_PATH", "/tmp/opencode-sessions"
)


def _get_runtime_arn() -> str:
    """Resolve the AgentCore runtime ARN.

    Checks RUNTIME_ARN first (direct), then constructs from
    RUNTIME_ARN_PREFIX + runtime ID discovered via the AgentCore SDK.
    """
    arn = os.environ.get("RUNTIME_ARN") or os.environ.get("OPENCODE_RUNTIME_ARN", "")
    if arn:
        return arn
    prefix = os.environ.get("RUNTIME_ARN_PREFIX", "")
    runtime_id = os.environ.get("AGENT_RUNTIME_ID", "")
    if prefix and runtime_id:
        return f"{prefix}{runtime_id}"
    return ""


# ---------------------------------------------------------------------------
# Helper: build a work directory under managed session storage
# ---------------------------------------------------------------------------
def _work_dir_for_job(job_id: str) -> str:
    """Return a work directory path under managed session storage."""
    path = os.path.join(SESSION_STORAGE_PATH, job_id)
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Tool 1: code (sync) — Req 1.1, 2.1-2.7, 3.1-3.4
# ---------------------------------------------------------------------------
@mcp.tool()
async def code(
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str = "",
    timeout_minutes: int = 10,
    _user_id: str = "",
    ctx: Context | None = None,
) -> dict:
    """Execute a coding task synchronously and return the result.

    Use this tool for quick, focused tasks (file creation, small edits,
    config changes) where you want the PR URL back immediately in the
    same conversation turn. The connection stays open for the full
    duration (typically 10-30 seconds). Progress is streamed. If git
    credentials are missing, an OAuth consent prompt is shown inline.

    Prefer run_coding_task (async) instead when the task is complex
    (multi-file refactors, large features) and may take several minutes,
    or when you want to fire-and-forget and check status later.
    """
    # --- Validation ---
    if not _user_id:
        return {"status": "failed", "error": "No user_id available"}
    if timeout_minutes < 1 or timeout_minutes > 30:
        return {
            "status": "failed",
            "error": "timeout_minutes must be between 1 and 30",
        }

    job_id = str(uuid.uuid4())
    branch = target_branch or f"opencode/{job_id}"
    work_dir = _work_dir_for_job(job_id)

    async def _on_progress(progress: int, total: int, message: str) -> None:
        await ctx.report_progress(progress=progress, total=total, message=message)

    async def _on_oauth_needed(auth_url: str) -> bool:
        elicit_result = await _elicit_with_timeout(
            ctx,
            message=(
                "Please authorize git access.\n\n"
                f"Open: {auth_url}\n\n"
                "Confirm when done."
            ),
            schema={
                "type": "object",
                "properties": {
                    "confirmation": {"type": "string", "default": "done"}
                },
            },
        )
        if elicit_result is None:
            # Timeout or elicitation exception — surface a user-friendly
            # credential-not-connected error rather than the terse
            # "OAuth authorization cancelled" message. The generic pipeline
            # handler stringifies this RuntimeError into the response's
            # `error` field unchanged. Per Property 1 in design.md, the
            # `error` field must equal GIT_HOST_NOT_CONNECTED_MESSAGE
            # exactly — the authorization URL is surfaced separately
            # through the `connect_git_host` tool's `action_required`
            # response, not by appending to this error string.
            raise RuntimeError(GIT_HOST_NOT_CONNECTED_MESSAGE)
        if getattr(elicit_result, "action", None) == "cancel":
            # Genuine user cancellation — preserve the existing
            # "OAuth authorization cancelled" pipeline path.
            return False
        return True

    return await run_coding_pipeline(
        user_id=_user_id,
        job_id=job_id,
        task_description=task_description,
        repo_url=repo_url,
        base_branch=base_branch,
        target_branch=branch,
        work_dir=work_dir,
        timeout_minutes=timeout_minutes,
        metric_prefix="code",
        on_progress=_on_progress,
        on_oauth_needed=_on_oauth_needed,
        cancel_flag=None,
    )


# ---------------------------------------------------------------------------
# Tool 2: run_coding_task (async) — Req 4.1-4.5, 5.1, 5.2
# ---------------------------------------------------------------------------
@mcp.tool()
async def run_coding_task(
    task_description: str,
    repo_url: str,
    base_branch: str,
    target_branch: str = "",
    timeout_minutes: int = 10,
    _user_id: str = "",
    ctx: Context | None = None,
) -> dict:
    """Submit a coding task for background execution. Returns a job_id immediately.

    Use this tool for complex or long-running tasks (multi-file refactors,
    large features, test suites) where you don't want to block the
    conversation. Poll with get_task_status to check progress. The task
    runs in the background and creates a PR when done.

    If git credentials are missing, the task fails immediately with
    'git_host_not_connected' -- call connect_git_host first.

    Prefer code (sync) instead for quick tasks where you want the PR
    URL back in the same turn.
    """
    if not _user_id:
        return {"status": "failed", "error": "No user_id available"}
    if timeout_minutes < 1 or timeout_minutes > 30:
        return {
            "status": "failed",
            "error": "timeout_minutes must be between 1 and 30",
        }

    job_id = str(uuid.uuid4())
    branch = target_branch or f"opencode/{job_id}"
    work_dir = _work_dir_for_job(job_id)

    # Capture runtime_session_id from request header (Req 4.4); the pipeline
    # persists it into the initial RUNNING DynamoDB row so cancel_task can
    # fall back to StopRuntimeSession.
    runtime_session_id = ""
    if ctx and hasattr(ctx, "request") and ctx.request:
        runtime_session_id = (ctx.request.headers or {}).get(
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id", ""
        )

    # Register with AgentCore async task management (Req 4.2, 15.1)
    app.add_async_task(job_id)

    # Set up cancellation flag (Req 7.1)
    _cancel_flags[job_id] = False

    async def _background() -> None:
        try:
            await run_coding_pipeline(
                user_id=_user_id,
                job_id=job_id,
                task_description=task_description,
                repo_url=repo_url,
                base_branch=base_branch,
                target_branch=branch,
                work_dir=work_dir,
                timeout_minutes=timeout_minutes,
                metric_prefix="async_task",
                runtime_session_id=runtime_session_id,
                on_progress=None,
                on_oauth_needed=None,
                cancel_flag=lambda: _cancel_flags.get(job_id, False),
            )
        finally:
            try:
                app.complete_async_task(job_id)
            except Exception:
                logger.exception(
                    "Failed to complete_async_task for job %s", job_id
                )
            _running_tasks.pop(job_id, None)
            _cancel_flags.pop(job_id, None)

    _running_tasks[job_id] = asyncio.create_task(_background())

    # Return immediately (Req 4.3)
    return {"job_id": job_id, "status": "RUNNING"}


# ---------------------------------------------------------------------------
# Tool 3: connect_git_host (interactive) — Req 1.2
# ---------------------------------------------------------------------------
@mcp.tool()
async def connect_git_host(git_host: str, _user_id: str = "", ctx: Context | None = None) -> dict:
    """Connect a git host (GitHub) by completing OAuth authorization.

    Run this before submitting coding tasks to a new git host.
    """
    if not git_host:
        return _fail("", "git_host is required")

    user_id = _user_id
    if not user_id:
        return _fail(git_host, "No user_id available")

    # 1. Check existing credentials
    try:
        access_token, auth_url = _get_credential(user_id, git_host)
    except Exception as exc:
        err = str(exc)
        if "NoCredentialProvider" in err or "ResourceNotFoundException" in err:
            return _fail(git_host, f"No credential provider registered for '{git_host}'. Contact your administrator.")
        return _fail(git_host, f"Failed to check git host credentials: {err}")

    if access_token:
        return _ok("already_connected", git_host, f"Already connected to {git_host}.")

    # 2. Elicit — present auth URL to user
    if ctx is None:
        return _fail(git_host, "No MCP context available for elicitation")

    elicit_msg = (
        f"Please authorize git access for {git_host}.\n\n"
        f"Open this URL in your browser to authorize:\n{auth_url}\n\n"
        "After authorizing, return here and confirm."
    )

    try:
        result = await _elicit_with_timeout(
            ctx,
            message=elicit_msg,
            schema={
                "type": "object",
                "properties": {
                    "confirmation": {
                        "type": "string",
                        "description": "Type 'done' after completing authorization in your browser",
                        "default": "done",
                    }
                },
            },
        )
    except Exception:
        # Elicitation not supported or failed — fall back to returning URL
        return {
            "status": "action_required",
            "git_host": git_host,
            "message": (
                f"Please open this URL in your browser to authorize git access for {git_host}:\n\n"
                f"{auth_url}\n\n"
                "After authorizing, call connect_git_host again to verify the connection."
            ),
            "authorization_url": auth_url,
        }

    if result is None or getattr(result, "action", None) == "cancel":
        # User cancelled or client doesn't support elicitation — return URL directly
        return {
            "status": "action_required",
            "git_host": git_host,
            "message": (
                f"Please open this URL in your browser to authorize git access for {git_host}:\n\n"
                f"{auth_url}\n\n"
                "After authorizing, call connect_git_host again to verify the connection."
            ),
            "authorization_url": auth_url,
        }

    # 3. Verify token after user confirms
    for _attempt in range(2):
        try:
            access_token, _ = _get_credential(user_id, git_host)
            if access_token:
                return _ok("connected", git_host, f"Successfully connected to {git_host}.")
        except Exception:
            pass

    return _fail(
        git_host,
        "Authorization not detected. Please try again and ensure you complete the OAuth flow in your browser.",
    )


# ---------------------------------------------------------------------------
# Tool 4: get_task_status (query) — Req 1.3
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_task_status(job_id: str, _user_id: str = "") -> dict:
    """Get the status of a coding task by job_id.

    Queries DynamoDB scoped to the authenticated user.
    """
    if not _user_id:
        return {"error": "No user_id available"}

    record = await query_job_record(job_id=job_id, user_id=_user_id)
    if not record:
        return {"error": "Job not found"}

    return {
        "job_id": record.get("job_id", ""),
        "status": record.get("status", ""),
        "task_description": record.get("task_description", ""),
        "repo_url": record.get("repo_url", ""),
        "base_branch": record.get("base_branch", ""),
        "target_branch": record.get("target_branch", ""),
        "pr_url": record.get("pr_url", ""),
        "stop_reason": record.get("stop_reason", ""),
        "files_edited": record.get("files_edited", []),
        "duration_seconds": record.get("duration_seconds", 0),
        "error": record.get("error", ""),
        "created_at": record.get("created_at", ""),
        "completed_at": record.get("completed_at", ""),
    }


# ---------------------------------------------------------------------------
# Tool 5: list_tasks (query) — Req 1.4
# ---------------------------------------------------------------------------
@mcp.tool()
async def list_tasks(
    status: str = "",
    limit: int = 50,
    _user_id: str = "",
) -> dict:
    """List coding tasks for the authenticated user.

    Optional status filter. Limit capped at 100.
    """
    if not _user_id:
        return {"error": "No user_id available"}

    return await query_user_jobs(
        user_id=_user_id,
        status_filter=status,
        limit=min(limit, 100),
    )


# ---------------------------------------------------------------------------
# Tool 6: cancel_task (control) — Req 1.5, 6.1, 6.2, 6.3
# ---------------------------------------------------------------------------
@mcp.tool()
async def cancel_task(job_id: str, _user_id: str = "") -> dict:
    """Cancel a running coding task.

    Tries in-process cancellation first (same microVM), then falls back
    to cross-session cancellation via StopRuntimeSession.
    Validates user ownership before executing.
    """
    if not _user_id:
        return {"error": "No user_id available"}

    # Query DynamoDB scoped to user
    record = await query_job_record(job_id=job_id, user_id=_user_id)
    if not record:
        return {"error": "Job not found"}

    # Reject terminal state jobs
    current_status = record.get("status", "")
    if current_status in ("COMPLETE", "FAILED", "CANCELLED"):
        return {"error": f"Job is already in terminal state: {current_status}"}

    # Attempt in-process cancellation first (Req 6.1)
    in_process_attempted = False
    if job_id in _running_tasks:
        in_process_attempted = True
        try:
            _cancel_flags[job_id] = True
            _running_tasks[job_id].cancel()
            logger.info("In-process cancellation signaled for job %s", job_id)
        except Exception:
            logger.warning(
                "In-process cancellation failed for job %s — falling back to StopRuntimeSession",
                job_id,
            )
            in_process_attempted = False  # fall through to cross-session

    # Fall back to StopRuntimeSession if not in-process or in-process failed (Req 6.2)
    if not in_process_attempted:
        session_id = record.get("runtime_session_id", "")
        if session_id:
            runtime_arn = _get_runtime_arn()
            if not runtime_arn:
                logger.warning(
                    "Cannot call StopRuntimeSession: runtime ARN unresolved (job %s)", job_id
                )
            else:
                try:
                    import boto3
                    client = boto3.client(
                        "bedrock-agentcore",
                        region_name=REGION,
                    )
                    client.stop_runtime_session(
                        agentRuntimeArn=runtime_arn,
                        runtimeSessionId=session_id,
                    )
                except Exception:
                    logger.warning(
                        "StopRuntimeSession failed for job %s session %s -- "
                        "proceeding with DynamoDB update",
                        job_id, session_id,
                    )

    # Always update DynamoDB to CANCELLED regardless of cancellation path (Req 6.3)
    await update_job_status(
        job_id=job_id, user_id=_user_id, status="CANCELLED",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    return {"job_id": job_id, "status": "CANCELLED"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Fail fast if OPENCODE_BINARY is misconfigured, so a broken
    # container fails at startup instead of on the first coding tool
    # call. See container.tools.run_opencode_acp._validate_opencode_binary
    # for the contract.
    from container.tools.run_opencode_acp import (
        OPENCODE_BINARY,
        _validate_opencode_binary,
    )
    _validate_opencode_binary(OPENCODE_BINARY)

    logger.info("Starting FastMCP on port 8000 (%.1fs since module load)", time.time() - _startup_start)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
