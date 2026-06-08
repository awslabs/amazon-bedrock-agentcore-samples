# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration test: async ``run_coding_task`` -> ``get_task_status`` flow.

Submits an async task, lets the background pipeline complete, then polls
get_task_status to verify the DynamoDB record transitions RUNNING -> COMPLETE.
Verifies add_async_task and complete_async_task called correctly.

After the pipeline-extraction refactor (spec ``pipeline-extraction-refactor``),
the 5-step coding pipeline lives in ``container.pipeline.run_coding_pipeline``
and the ``_run_background_pipeline`` helper in ``container.code_mcp_server``
has been deleted. These tests exercise the thin MCP glue in
``run_coding_task`` by patching ``container.code_mcp_server.run_coding_pipeline``
directly; the pipeline's own behavior is covered by
``tests/unit/test_pipeline.py`` and ``tests/property/test_pipeline_properties.py``.

Requirements: 4.1, 4.2, 4.3, 4.6, 22.1, 22.3
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub external dependencies
# ---------------------------------------------------------------------------
fastmcp_mock = MagicMock()
fastmcp_mock.FastMCP.return_value.tool.return_value = lambda fn: fn
sys.modules.setdefault("fastmcp", fastmcp_mock)

agentcore_mock = MagicMock()
agentcore_mock.BedrockAgentCoreApp.return_value = MagicMock()
sys.modules.setdefault("bedrock_agentcore", agentcore_mock)
sys.modules.setdefault("bedrock_agentcore.runtime", agentcore_mock)

strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules.setdefault("strands", strands_mock)

from container.code_mcp_server import (  # noqa: E402
    run_coding_task,
    get_task_status,
    _running_tasks,
    _cancel_flags,
)


async def _drain_background_task(job_id: str) -> None:
    """Await the background task spawned by ``run_coding_task`` if present.

    The background coroutine cleans up ``_running_tasks[job_id]`` and
    ``_cancel_flags[job_id]`` in its ``finally`` block, so after draining
    neither key is expected to be present. Exceptions from the mocked
    pipeline are swallowed (the ``finally`` block still runs).
    """
    task = _running_tasks.get(job_id)
    if task is None:
        return
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


class TestAsyncFlow:
    """Submit async task, verify immediate return, then poll until COMPLETE."""

    @pytest.mark.asyncio
    async def test_submit_returns_running_immediately(self):
        """Verify job_id returned immediately with status RUNNING (Req 4.3)."""
        mock_app = MagicMock()
        mock_pipeline = AsyncMock(
            return_value={
                "status": "complete",
                "pr_url": "https://github.com/o/r/pull/1",
                "stop_reason": "end_turn",
                "files_edited": [],
                "duration_seconds": 1.0,
            }
        )

        with (
            patch("container.code_mcp_server.app", mock_app),
            patch(
                "container.code_mcp_server.run_coding_pipeline",
                mock_pipeline,
            ),
        ):
            result = await run_coding_task(
                task_description="Add tests",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
            )

            assert result["status"] == "RUNNING"
            assert "job_id" in result
            # Validate UUID format
            uuid.UUID(result["job_id"])

            # Let the background coroutine run its finally block so that
            # _running_tasks / _cancel_flags are cleaned up deterministically.
            await _drain_background_task(result["job_id"])

        assert result["job_id"] not in _running_tasks
        assert result["job_id"] not in _cancel_flags

    @pytest.mark.asyncio
    async def test_add_async_task_called(self):
        """Verify app.add_async_task(job_id) called before return (Req 4.2)."""
        mock_app = MagicMock()
        mock_pipeline = AsyncMock(
            return_value={
                "status": "complete",
                "pr_url": "",
                "stop_reason": "end_turn",
                "files_edited": [],
                "duration_seconds": 0.1,
            }
        )

        with (
            patch("container.code_mcp_server.app", mock_app),
            patch(
                "container.code_mcp_server.run_coding_pipeline",
                mock_pipeline,
            ),
        ):
            result = await run_coding_task(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
            )

            mock_app.add_async_task.assert_called_once_with(result["job_id"])

            await _drain_background_task(result["job_id"])

    @pytest.mark.asyncio
    async def test_runtime_session_id_forwarded_to_pipeline(self):
        """Verify ``runtime_session_id`` is extracted from request headers and forwarded.

        The handler extracts the ``X-Amzn-Bedrock-AgentCore-Runtime-Session-Id``
        header and passes it to ``run_coding_pipeline`` as a kwarg. The pipeline
        (mocked here) is what persists the RUNNING row with that session id; the
        handler no longer writes DynamoDB directly.
        """
        mock_app = MagicMock()
        mock_pipeline = AsyncMock(
            return_value={
                "status": "complete",
                "pr_url": "",
                "stop_reason": "end_turn",
                "files_edited": [],
                "duration_seconds": 0.1,
            }
        )

        # Build a mock ctx with a request exposing the runtime-session-id header.
        mock_ctx = MagicMock()
        mock_ctx.request = MagicMock()
        mock_ctx.request.headers = {
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "session-xyz",
        }

        with (
            patch("container.code_mcp_server.app", mock_app),
            patch(
                "container.code_mcp_server.run_coding_pipeline",
                mock_pipeline,
            ),
        ):
            result = await run_coding_task(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
                ctx=mock_ctx,
            )

            await _drain_background_task(result["job_id"])

        # Pipeline was awaited with runtime_session_id forwarded from the header.
        mock_pipeline.assert_awaited_once()
        call_kwargs = mock_pipeline.await_args.kwargs
        assert call_kwargs["runtime_session_id"] == "session-xyz"
        assert call_kwargs["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_background_task_cleans_up_on_completion(self):
        """Verify background ``finally`` block runs on successful completion.

        After the pipeline returns, ``app.complete_async_task(job_id)`` must
        be invoked and the job entry must be removed from ``_running_tasks``
        and ``_cancel_flags`` (Req 4.6, 22.1, 22.3).

        Pre-refactor this was asserted by calling ``_run_background_pipeline``
        directly. That helper has been deleted by the pipeline-extraction
        refactor; the equivalent bookkeeping now lives in the inline
        ``_background()`` coroutine inside ``run_coding_task``, so the test
        exercises ``run_coding_task`` end-to-end and awaits the spawned task.
        """
        mock_app = MagicMock()
        mock_pipeline = AsyncMock(
            return_value={
                "status": "complete",
                "pr_url": "https://github.com/o/r/pull/1",
                "stop_reason": "end_turn",
                "files_edited": ["src/main.py"],
                "duration_seconds": 2.5,
            }
        )

        with (
            patch("container.code_mcp_server.app", mock_app),
            patch(
                "container.code_mcp_server.run_coding_pipeline",
                mock_pipeline,
            ),
        ):
            result = await run_coding_task(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                target_branch="feature",
                _user_id="user-1",
            )

            job_id = result["job_id"]

            # Await the spawned background task so its ``finally`` block runs.
            await _drain_background_task(job_id)

        # Pipeline was awaited exactly once with the expected argument set.
        mock_pipeline.assert_awaited_once()
        call_kwargs = mock_pipeline.await_args.kwargs
        assert call_kwargs["user_id"] == "user-1"
        assert call_kwargs["job_id"] == job_id
        assert call_kwargs["target_branch"] == "feature"
        assert call_kwargs["metric_prefix"] == "async_task"

        # complete_async_task called for cleanup (Req 22.3).
        mock_app.complete_async_task.assert_called_once_with(job_id)
        # Job removed from in-process registries.
        assert job_id not in _running_tasks
        assert job_id not in _cancel_flags

    @pytest.mark.asyncio
    async def test_background_task_cleans_up_on_failure(self):
        """Cleanup still runs when the pipeline raises unexpectedly.

        ``run_coding_pipeline`` is contracted to never raise, but the
        inline ``_background()`` coroutine still wraps it in a ``finally``
        block so that ``complete_async_task`` and registry cleanup run even
        if a bug causes the pipeline to propagate an exception. This test
        pins that behavior.
        """
        mock_app = MagicMock()
        mock_pipeline = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch("container.code_mcp_server.app", mock_app),
            patch(
                "container.code_mcp_server.run_coding_pipeline",
                mock_pipeline,
            ),
        ):
            result = await run_coding_task(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
            )

            job_id = result["job_id"]
            await _drain_background_task(job_id)

        mock_app.complete_async_task.assert_called_once_with(job_id)
        assert job_id not in _running_tasks
        assert job_id not in _cancel_flags

    @pytest.mark.asyncio
    async def test_get_task_status_returns_record(self):
        """Verify get_task_status returns the DynamoDB record (Req 4.3)."""
        fake_record = {
            "job_id": "abc-123",
            "status": "COMPLETE",
            "task_description": "task",
            "repo_url": "https://github.com/o/r",
            "base_branch": "main",
            "target_branch": "feature",
            "pr_url": "https://github.com/o/r/pull/1",
            "stop_reason": "end_turn",
            "files_edited": ["src/main.py"],
            "duration_seconds": 42,
            "error": "",
            "created_at": "2025-01-01T00:00:00+00:00",
            "completed_at": "2025-01-01T00:01:00+00:00",
        }

        with patch(
            "container.code_mcp_server.query_job_record",
            new_callable=AsyncMock,
            return_value=fake_record,
        ):
            result = await get_task_status(job_id="abc-123", _user_id="user-1")

        assert result["status"] == "COMPLETE"
        assert result["pr_url"] == "https://github.com/o/r/pull/1"
        assert result["stop_reason"] == "end_turn"
        assert result["files_edited"] == ["src/main.py"]
