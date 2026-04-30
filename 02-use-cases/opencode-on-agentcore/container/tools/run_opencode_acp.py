# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Run OpenCode via ACP protocol over stdin/stdout.

Design notes for running OpenCode inside the AgentCore microVM:

* OpenCode is distributed as a Bun-compiled binary. Bun extracts its virtual
  filesystem (``bunfs``) to ``/tmp`` on first run; any read-only or
  PRoot-like isolation breaks it (GitHub issues #7960, #7843). The microVM
  writable ``/tmp`` works, but we also install via the npm package so the
  same binary path is a plain JS bundle when possible.
* All OpenCode startup side effects (autoupdate check, LSP download,
  models.dev fetch, data-dir prune, default plugin load) hang or fail in
  the microVM. Disable them all via ``OPENCODE_DISABLE_*`` env vars
  (plumbed at runtime env + per-spawn).
* Config is passed inline via ``OPENCODE_CONFIG_CONTENT`` so the binary
  never has to read a file. Avoids any ``cwd`` / HOME lookup surprises.
* We do **not** pre-drain stderr before sending ACP frames. ``opencode acp``
  is ready for stdin as soon as it starts; waiting on stderr to see a
  "migration complete" line is brittle and sometimes deadlocks because the
  binary interleaves stderr and the ACP reply stream.
"""

import asyncio
import json
import logging
import os
import signal
import time
from typing import Callable, Optional, TypedDict

logger = logging.getLogger(__name__)
OPENCODE_BINARY = os.environ.get("OPENCODE_BINARY", "/usr/local/bin/opencode")


def _validate_opencode_binary(path: str) -> None:
    """Fail fast at server startup if ``OPENCODE_BINARY`` is unusable.

    Called once from ``container/code_mcp_server.py`` before the
    FastMCP server starts listening; not called per-invocation, so
    unit tests of ``run_opencode_acp_impl`` that mock
    ``asyncio.create_subprocess_exec`` are unaffected.

    The binary path is deployment-time config (read once at import),
    not user input, so this is defence in depth rather than sandbox
    boundary enforcement. We check:

    * The value is a non-empty string.
    * The path is absolute. ``subprocess.create_subprocess_exec`` with
      a relative name would resolve via ``$PATH``, which is noisy
      inside the microVM and makes it harder to reason about which
      binary actually ran.
    * The path exists and is an executable regular file.

    Raised as ``RuntimeError`` so the startup path surfaces the
    misconfiguration with a clear message rather than a generic
    ``FileNotFoundError`` from deep inside ``create_subprocess_exec``
    on the first incoming request.
    """
    if not isinstance(path, str) or not path:
        raise RuntimeError("OPENCODE_BINARY must be a non-empty string")
    if not os.path.isabs(path):
        raise RuntimeError(
            f"OPENCODE_BINARY must be an absolute path; got {path!r}"
        )
    if not os.path.isfile(path):
        raise RuntimeError(
            f"OPENCODE_BINARY does not exist or is not a regular file: {path!r}"
        )
    if not os.access(path, os.X_OK):
        raise RuntimeError(
            f"OPENCODE_BINARY is not executable: {path!r}"
        )


class OpenCodeResult(TypedDict):
    stdout: str
    stderr: str
    stop_reason: str          # from PromptResponse.stopReason: "end_turn", "max_tokens", "max_requests", "refused", "cancelled"
    files_edited: list[str]   # from tool_call/tool_call_update notifications with locations
    plan: list[dict]          # from plan notifications: [{"content": "...", "status": "..."}]


ProgressCallback = Optional[Callable[[str], None]]

# ACP JSON-RPC message IDs
_INIT_ID = 1
_SESSION_NEW_ID = 2
_SESSION_PROMPT_ID = 3


def _make_jsonrpc(id: int, method: str, params: dict) -> str:
    """Build a JSON-RPC 2.0 request string (newline-delimited)."""
    msg = {"jsonrpc": "2.0", "id": id, "method": method, "params": params}
    return json.dumps(msg) + "\n"


def _build_opencode_config() -> dict:
    """Build the inline OpenCode config dict.

    OpenCode v1.14+ has strict config validation — only known keys are
    allowed. The ``amazon-bedrock`` provider and its global-prefixed
    cross-region inference profiles (including
    ``global.anthropic.claude-opus-4-6-v1``) are built in, so we do not
    redeclare them in ``provider.amazon-bedrock.models`` — that only
    muddles resolution. We simply set the ``model`` field to point at
    the prefixed ID. The provider reads AWS credentials from the
    environment (IAM role on AgentCore, via the AWS SDK's default
    credential provider chain).
    """
    model_id = os.environ.get("OPENCODE_MODEL", "global.anthropic.claude-opus-4-6-v1")
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": f"amazon-bedrock/{model_id}",
        "permission": {
            "edit": "allow",
            "bash": "allow",
        },
        "autoupdate": False,
        "disabled_providers": ["opencode"],
    }


async def _read_line(stdout: asyncio.StreamReader, timeout: float) -> Optional[str]:
    """Read a single line from stdout with timeout. Returns None on EOF."""
    try:
        line = await asyncio.wait_for(stdout.readline(), timeout=timeout)
        if not line:
            return None
        return line.decode("utf-8").strip()
    except asyncio.TimeoutError:
        raise


async def _send_message(stdin: asyncio.StreamWriter, message: str) -> None:
    """Send a JSON-RPC message over stdin."""
    try:
        stdin.write(message.encode("utf-8"))
        await stdin.drain()
    except (BrokenPipeError, ConnectionResetError) as exc:
        raise RuntimeError(f"OpenCode stdin closed: {exc}") from exc


async def _drain_stderr(proc: asyncio.subprocess.Process, buffer: list[str]) -> None:
    """Continuously read stderr into ``buffer`` so the pipe never fills up.

    A full stderr pipe will eventually block the child. This coroutine
    runs for the lifetime of the process and accumulates lines for
    post-mortem diagnostics.
    """
    if proc.stderr is None:
        return
    try:
        while True:
            line = await proc.stderr.readline()
            if not line:
                return
            decoded = line.decode("utf-8", errors="replace").rstrip()
            buffer.append(decoded)
            # Keep buffer bounded
            if len(buffer) > 500:
                del buffer[:-250]
            logger.info("OpenCode stderr: %s", decoded)
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logger.warning("stderr drain error: %s", exc)


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    """Terminate process with SIGTERM → SIGKILL escalation (5s grace)."""
    if proc.returncode is not None:
        return

    try:
        proc.send_signal(signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return

    try:
        await asyncio.wait_for(proc.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except (ProcessLookupError, OSError):
            pass
        try:
            await proc.wait()
        except Exception:
            pass


def _resolve_aws_credentials_into_env() -> dict:
    """Resolve AWS IAM-role credentials via boto3 and return them as env vars.

    The AgentCore microVM vends IAM-role credentials exclusively via
    IMDSv2 (at ``169.254.169.254``, role name ``execution_role``).
    Python boto3's default provider chain finds them fine.

    OpenCode's ``amazon-bedrock`` provider, however, short-circuits to
    ``autoload: false`` if NONE of these env sources are set:

    * ``AWS_PROFILE``
    * ``AWS_ACCESS_KEY_ID``
    * ``AWS_BEARER_TOKEN_BEDROCK``
    * ``AWS_WEB_IDENTITY_TOKEN_FILE``
    * ``AWS_CONTAINER_CREDENTIALS_{RELATIVE,FULL}_URI``

    IMDS is **not** in that gate (confirmed in upstream
    ``packages/opencode/src/provider/provider.ts``). The gate runs
    before ``fromNodeProviderChain()`` is ever called, so even though
    the Node SDK's default chain would pick up IMDS, the provider is
    never loaded and Bedrock calls silently return ``end_turn`` with
    zero tokens.

    Workaround: resolve the IAM role snapshot via boto3 and export it
    as classic env vars. Creds are valid for ~6 hours; coding sessions
    run for minutes; each subprocess spawn re-resolves fresh creds.
    """
    try:
        import boto3
        session = boto3.Session()
        creds = session.get_credentials()
        if creds is None:
            return {}
        frozen = creds.get_frozen_credentials()
        out = {
            "AWS_ACCESS_KEY_ID": frozen.access_key,
            "AWS_SECRET_ACCESS_KEY": frozen.secret_key,
        }
        if frozen.token:
            out["AWS_SESSION_TOKEN"] = frozen.token
        return out
    except Exception as exc:
        logger.warning("Failed to resolve AWS credentials for OpenCode: %s", exc)
        return {}


def _build_spawn_env(work_dir: str) -> dict:
    """Env vars for the OpenCode subprocess.

    Scoped to what is proven needed to get OpenCode running headlessly.
    """
    # Resolve IAM-role creds via boto3 so we can pass them as classic env
    # vars. OpenCode's amazon-bedrock provider short-circuits to
    # ``autoload: false`` if AWS_ACCESS_KEY_ID (and a few other env
    # sources) are not set — IMDS alone does not satisfy its gate. See
    # the ``_resolve_aws_credentials_into_env`` docstring.
    aws_creds = _resolve_aws_credentials_into_env()
    return {
        **os.environ,
        **aws_creds,
        # Autoupdate would try to download a new OpenCode binary on every
        # microVM cold start (new fs each session).
        "OPENCODE_DISABLE_AUTOUPDATE": "true",
    }


def _write_opencode_config(work_dir: str) -> None:
    """Write ``opencode.json`` to ``work_dir``.

    OpenCode v1.14+ searches for ``opencode.json`` in the current
    directory. Writing a file avoids the ``OPENCODE_CONFIG_CONTENT``
    inline-env-var path, matching the ergonomics of the OpenCode CLI.
    """
    from pathlib import Path as _P
    config_path = _P(work_dir) / "opencode.json"
    config_path.write_text(json.dumps(_build_opencode_config()))


async def run_opencode_acp_impl(
    work_dir: str,
    task_description: str,
    timeout_seconds: int,
    on_progress: ProgressCallback = None,
) -> OpenCodeResult:
    """Core implementation: spawn OpenCode via ACP protocol over stdin/stdout.

    Supports a ``on_progress`` callback (used by the async task to emit
    MCP progress notifications). The synchronous code tool omits it.
    """
    _write_opencode_config(work_dir)
    collected_stdout: list[str] = []
    stderr_buffer: list[str] = []
    files_edited: list[str] = []
    plan_entries: list[dict] = []
    stop_reason = "end_turn"
    spawn_env = _build_spawn_env(work_dir)

    logger.info(
        "Spawning OpenCode: binary=%s cwd=%s model=%s",
        OPENCODE_BINARY, work_dir, spawn_env.get("OPENCODE_MODEL"),
    )

    proc = await asyncio.create_subprocess_exec(
        OPENCODE_BINARY, "acp", "--log-level", "INFO",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=work_dir,
        env=spawn_env,
    )

    # Drain stderr in the background so the pipe never fills up.
    stderr_task = asyncio.create_task(_drain_stderr(proc, stderr_buffer))

    try:
        assert proc.stdin is not None
        assert proc.stdout is not None

        remaining = float(timeout_seconds)

        # Step 1: Send initialize (no pre-drain of stderr — ACP accepts
        # stdin as soon as the process starts).
        await _send_message(
            proc.stdin,
            _make_jsonrpc(_INIT_ID, "initialize", {
                "protocolVersion": 1,
                "capabilities": {},
            }),
        )

        init_response = await _read_line(proc.stdout, timeout=remaining)
        if init_response is None:
            await asyncio.sleep(0.2)  # let stderr drain catch up
            stderr_snapshot = "\n".join(stderr_buffer[-30:])
            raise RuntimeError(
                f"OpenCode closed stdout before initialize response. "
                f"stderr tail: {stderr_snapshot[:1500]}"
            )

        try:
            init_parsed = json.loads(init_response)
            agent_info = init_parsed.get("result", {}).get("agentInfo", {})
            logger.info(
                "OpenCode ACP initialized: version=%s",
                agent_info.get("version", "?"),
            )
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Could not parse init response: %s", init_response[:200])

        # Step 2: Send session/new
        await _send_message(
            proc.stdin,
            _make_jsonrpc(_SESSION_NEW_ID, "session/new", {
                "cwd": work_dir,
                "mcpServers": [],
            }),
        )

        session_response_line = await _read_line(proc.stdout, timeout=remaining)
        if session_response_line is None:
            raise RuntimeError("OpenCode closed stdout before session/new response")

        session_response = json.loads(session_response_line)
        session_id = session_response.get("result", {}).get("sessionId", "")
        if not session_id:
            raise RuntimeError(
                f"No sessionId in session/new response: {session_response_line}"
            )

        _meta = session_response.get("result", {}).get("_meta", {}).get("opencode", {})
        selected_model = _meta.get("modelId", "unknown")
        logger.info(
            "OpenCode ACP session created: session_id=%s, model=%s",
            session_id, selected_model,
        )

        # Step 3: Send session/prompt
        logger.info("Sending session/prompt (task len=%d)", len(task_description))
        try:
            await _send_message(
                proc.stdin,
                _make_jsonrpc(_SESSION_PROMPT_ID, "session/prompt", {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": task_description}],
                }),
            )
            logger.info("session/prompt sent successfully")
        except Exception as exc:
            logger.error("Failed to send session/prompt: %s", exc)
            raise

        # Step 4: Read stdout, parsing responses and notifications
        deadline = time.monotonic() + remaining
        iteration = 0

        while True:
            iteration += 1
            time_left = deadline - time.monotonic()
            if time_left <= 0:
                raise asyncio.TimeoutError("OpenCode execution timed out")

            try:
                line = await _read_line(proc.stdout, timeout=time_left)
            except asyncio.TimeoutError:
                raise
            except Exception as exc:
                logger.error("read_line raised on iter %d: %s", iteration, exc)
                raise

            if line is None:
                # EOF — process exited without sending the final response.
                await asyncio.sleep(0.2)  # let stderr drain catch up
                logger.warning(
                    "OpenCode stdout EOF at iter=%d before prompt response. "
                    "stderr tail: %s",
                    iteration,
                    "\n".join(stderr_buffer[-30:])[:1500],
                )
                break

            if not line:
                continue

            logger.debug("Received line (iter=%d, len=%d): %s",
                         iteration, len(line), line[:300])

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                collected_stdout.append(line)
                continue

            # Notification (no "id"): progress / tool updates / plan
            if "method" in msg and "id" not in msg:
                method = msg["method"]
                params = msg.get("params", {})

                if method == "session/update":
                    update = params.get("update", {})
                    update_type = update.get("sessionUpdate", "")

                    if update_type == "agent_message_chunk":
                        content = update.get("content", {})
                        text = content.get("text", "")
                        if text:
                            collected_stdout.append(text)
                            if on_progress:
                                on_progress(text[:200])

                    elif update_type == "tool_call":
                        title = update.get("title", "")
                        for loc in update.get("locations", []):
                            uri = loc.get("uri", "") if isinstance(loc, dict) else str(loc)
                            if uri and uri not in files_edited:
                                files_edited.append(uri)
                        if title and on_progress:
                            on_progress(title)

                    elif update_type == "tool_call_update":
                        for loc in update.get("locations", []):
                            uri = loc.get("uri", "") if isinstance(loc, dict) else str(loc)
                            if uri and uri not in files_edited:
                                files_edited.append(uri)
                        title = update.get("title", "")
                        if title and on_progress:
                            on_progress(title)

                    elif update_type == "plan":
                        plan_entries.clear()
                        plan_entries.extend(update.get("entries", []))

                    else:
                        update_msg = params.get("message", "") or update.get("message", "")
                        if update_msg:
                            collected_stdout.append(update_msg)
                            if on_progress:
                                on_progress(update_msg)
                else:
                    collected_stdout.append(line)
                continue

            # Response to session/prompt (id == 3)
            if msg.get("id") == _SESSION_PROMPT_ID:
                result = msg.get("result", {})
                stop_reason = result.get("stopReason", "end_turn")
                usage = result.get("usage", {})
                total_tokens = usage.get("totalTokens", 0)
                logger.info(
                    "OpenCode ACP prompt completed: stop_reason=%s, "
                    "total_tokens=%s, input_tokens=%s, output_tokens=%s",
                    stop_reason,
                    total_tokens,
                    usage.get("inputTokens", 0),
                    usage.get("outputTokens", 0),
                )
                if "error" in msg:
                    raise RuntimeError(
                        f"OpenCode ACP error: {msg['error'].get('message', 'Unknown')}"
                    )
                if total_tokens == 0 and stop_reason == "end_turn":
                    # No model call happened — warn with context so we can debug.
                    logger.warning(
                        "OpenCode returned end_turn with 0 tokens — no LLM "
                        "call was made. Most likely cause: AWS creds not "
                        "reaching OpenCode's aws-sdk-js."
                    )
                break

            collected_stdout.append(line)

    except asyncio.TimeoutError:
        await _terminate_process(proc)
        stderr_task.cancel()
        try:
            await asyncio.wait_for(stderr_task, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        raise RuntimeError(
            f"OpenCode timed out after {timeout_seconds}s. "
            f"stderr tail: {chr(10).join(stderr_buffer[-30:])[:1000]}"
        )
    except Exception as exc:
        logger.exception("Unexpected error in OpenCode ACP loop: %s", exc)
        await _terminate_process(proc)
        raise
    finally:
        if proc.returncode is None:
            await _terminate_process(proc)
        stderr_task.cancel()
        try:
            await asyncio.wait_for(stderr_task, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

    collected_stderr = "\n".join(stderr_buffer)

    # A negative returncode means we terminated via signal (SIGTERM=-15,
    # SIGKILL=-9). When we've already broken out of the read loop with
    # a successful stop_reason, the SIGTERM we sent in ``finally`` is
    # expected and not a failure. Only raise on positive non-zero codes,
    # which indicate the binary itself exited with an error.
    if proc.returncode and proc.returncode > 0:
        logger.error(
            "OpenCode exited with code %d. stderr: %s",
            proc.returncode, collected_stderr[:1500],
        )
        raise RuntimeError(
            f"OpenCode exited with code {proc.returncode}. "
            f"stderr: {collected_stderr[:500]}"
        )

    return OpenCodeResult(
        stdout="\n".join(collected_stdout),
        stderr=collected_stderr,
        stop_reason=stop_reason,
        files_edited=files_edited,
        plan=plan_entries,
    )


async def run_opencode_acp(
    work_dir: str,
    task_description: str,
    timeout_seconds: int,
) -> OpenCodeResult:
    """Spawn OpenCode as subprocess via ACP protocol over stdin/stdout.

    Sends ACP initialize -> session/new -> session/prompt, parses
    session/update notifications for progress, and extracts stop_reason
    and files_edited from the final ACP response.
    Handles timeout with SIGTERM -> SIGKILL escalation.
    """
    return await run_opencode_acp_impl(
        work_dir=work_dir,
        task_description=task_description,
        timeout_seconds=timeout_seconds,
    )
