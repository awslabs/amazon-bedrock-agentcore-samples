# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration test: sync ``code`` tool end-to-end.

Verifies that the thin ``code`` MCP tool handler correctly wires FastMCP's
``ctx.report_progress`` and ``ctx.elicit`` into the pipeline's
``on_progress`` and ``on_oauth_needed`` callback slots, then returns the
``run_coding_pipeline`` result dict unchanged.

After the pipeline-extraction refactor (spec ``pipeline-extraction-refactor``),
the 5-step pipeline lives in ``container.pipeline.run_coding_pipeline``.
These tests patch ``container.code_mcp_server.run_coding_pipeline`` as an
``AsyncMock`` and inspect the callbacks it was called with to verify the
MCP glue. The pipeline's own behavior (step ordering, OAuth retry-once,
DynamoDB bookkeeping, metrics) is covered by
``tests/unit/test_pipeline.py`` and
``tests/property/test_pipeline_properties.py``.

Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 11.4, 11.5, 11.7
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub external dependencies before importing the server module.
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

from container.code_mcp_server import code  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    ctx.elicit = AsyncMock()
    return ctx


def _success_result(
    pr_url: str = "https://github.com/o/r/pull/42",
) -> dict:
    """Default success ``RunPipelineResult`` used by the AsyncMock."""
    return {
        "status": "complete",
        "pr_url": pr_url,
        "stop_reason": "end_turn",
        "files_edited": ["src/main.py"],
        "duration_seconds": 1.23,
    }


# ===================================================================
# Test: full pipeline success (Req 2.1, 2.2, 2.3)
# ===================================================================
class TestSyncCodeE2E:
    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        """``code`` returns the pipeline's success dict unchanged."""
        ctx = _make_ctx()
        pipeline_result = _success_result()

        with patch(
            "container.code_mcp_server.run_coding_pipeline",
            new_callable=AsyncMock,
            return_value=pipeline_result,
        ) as mock_pipeline:
            result = await code(
                task_description="Add unit tests",
                repo_url="https://github.com/owner/repo",
                base_branch="main",
                _user_id="user-123",
                ctx=ctx,
            )

        # ``code`` should return the pipeline's dict unchanged (Req 11.7).
        assert result == pipeline_result
        assert result["status"] == "complete"
        assert result["pr_url"] == "https://github.com/o/r/pull/42"
        assert result["stop_reason"] == "end_turn"
        assert result["files_edited"] == ["src/main.py"]
        assert result["duration_seconds"] == 1.23

        # Pipeline was awaited exactly once with the sync-path callback
        # configuration (Req 11.6).
        mock_pipeline.assert_awaited_once()
        call_kwargs = mock_pipeline.await_args.kwargs
        assert call_kwargs["user_id"] == "user-123"
        assert call_kwargs["on_progress"] is not None
        assert call_kwargs["on_oauth_needed"] is not None
        assert call_kwargs["cancel_flag"] is None
        assert call_kwargs["metric_prefix"] == "code"

    @pytest.mark.asyncio
    async def test_progress_callback_wires_ctx_report_progress(self):
        """The ``on_progress`` adapter calls ``ctx.report_progress`` (Req 11.4).

        After the refactor, ``code`` does not emit progress itself - it
        passes an ``on_progress`` closure to ``run_coding_pipeline``. This
        test captures that closure, invokes it as the pipeline would, and
        asserts it forwards to ``ctx.report_progress``.
        """
        ctx = _make_ctx()

        captured: dict = {}

        async def fake_pipeline(**kwargs):
            captured["on_progress"] = kwargs["on_progress"]
            # Simulate the 5 progress events the real pipeline emits.
            await kwargs["on_progress"](1, 5, "Cloning repository...")
            await kwargs["on_progress"](2, 5, "Running OpenCode...")
            await kwargs["on_progress"](3, 5, "Scanning for credentials...")
            await kwargs["on_progress"](4, 5, "Pushing changes...")
            await kwargs["on_progress"](5, 5, "Done")
            return _success_result()

        with patch(
            "container.code_mcp_server.run_coding_pipeline",
            side_effect=fake_pipeline,
        ):
            await code(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
                ctx=ctx,
            )

        progress_calls = ctx.report_progress.call_args_list
        assert len(progress_calls) == 5
        # First and last calls mirror the pipeline's fixed phase messages.
        assert progress_calls[0].kwargs == {
            "progress": 1,
            "total": 5,
            "message": "Cloning repository...",
        }
        assert progress_calls[-1].kwargs == {
            "progress": 5,
            "total": 5,
            "message": "Done",
        }

    @pytest.mark.asyncio
    async def test_oauth_adapter_confirms_returns_true(self):
        """The ``on_oauth_needed`` adapter returns True on elicit confirm (Req 11.5)."""
        ctx = _make_ctx()
        # ``ctx.elicit`` returns a non-None result whose ``action`` is not
        # ``"cancel"`` -> the adapter should return True.
        confirm_result = MagicMock()
        confirm_result.action = "submit"
        ctx.elicit.return_value = confirm_result

        captured: dict = {}

        async def fake_pipeline(**kwargs):
            captured["on_oauth_needed"] = kwargs["on_oauth_needed"]
            confirmed = await kwargs["on_oauth_needed"]("https://auth.example/login")
            captured["confirmed"] = confirmed
            return _success_result()

        with patch(
            "container.code_mcp_server.run_coding_pipeline",
            side_effect=fake_pipeline,
        ):
            result = await code(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
                ctx=ctx,
            )

        ctx.elicit.assert_called_once()
        assert captured["confirmed"] is True
        assert result["status"] == "complete"

    @pytest.mark.asyncio
    async def test_oauth_adapter_returns_false_on_cancel(self):
        """The ``on_oauth_needed`` adapter returns False when elicit is cancelled (Req 11.5).

        Pre-refactor this test asserted the final ``code`` result was
        ``failed`` after an OAuth cancel, which entangled the MCP glue
        with pipeline error classification. Post-refactor the pipeline
        owns error classification (covered in
        ``tests/unit/test_pipeline.py``) and this test focuses on the
        wiring: the adapter must return False when ``ctx.elicit`` signals
        cancel, and ``code`` must forward whatever dict the pipeline
        returns.
        """
        ctx = _make_ctx()
        cancel_result = MagicMock()
        cancel_result.action = "cancel"
        ctx.elicit.return_value = cancel_result

        captured: dict = {}

        async def fake_pipeline(**kwargs):
            captured["confirmed"] = await kwargs["on_oauth_needed"](
                "https://auth.example/login"
            )
            # Mirror the pipeline's real behavior on OAuth cancel.
            return {
                "status": "failed",
                "error": "OAuth authorization cancelled",
                "duration_seconds": 0.01,
            }

        with patch(
            "container.code_mcp_server.run_coding_pipeline",
            side_effect=fake_pipeline,
        ):
            result = await code(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
                ctx=ctx,
            )

        assert captured["confirmed"] is False
        assert result == {
            "status": "failed",
            "error": "OAuth authorization cancelled",
            "duration_seconds": 0.01,
        }

    @pytest.mark.asyncio
    async def test_oauth_adapter_raises_on_none(self):
        """Adapter raises ``RuntimeError`` when ``ctx.elicit`` returns None (Req 11.5).

        Post-spec-30 (elicitation-error-handling) contract: when
        ``_elicit_with_timeout`` returns ``None`` (timeout or caught
        elicitation exception), ``_on_oauth_needed`` raises
        ``RuntimeError(GIT_HOST_NOT_CONNECTED_MESSAGE)`` rather than
        returning ``False``. The returning-``False`` path is reserved
        for genuine user cancels (``result.action == "cancel"``), which
        is covered by ``test_oauth_adapter_returns_false_on_cancel``.
        """
        from container.lib.credential_errors import (
            GIT_HOST_NOT_CONNECTED_MESSAGE,
        )

        ctx = _make_ctx()
        ctx.elicit.return_value = None

        captured: dict = {}

        async def fake_pipeline(**kwargs):
            try:
                await kwargs["on_oauth_needed"]("https://auth.example/login")
            except RuntimeError as exc:
                captured["raised"] = exc
                return {
                    "status": "failed",
                    "error": str(exc),
                    "duration_seconds": 0.01,
                }
            return _success_result()

        with patch(
            "container.code_mcp_server.run_coding_pipeline",
            side_effect=fake_pipeline,
        ):
            result = await code(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
                ctx=ctx,
            )

        # The adapter raised RuntimeError with the canonical message,
        # not returned False.
        assert isinstance(captured.get("raised"), RuntimeError)
        assert str(captured["raised"]) == GIT_HOST_NOT_CONNECTED_MESSAGE
        assert result["status"] == "failed"
        assert result["error"] == GIT_HOST_NOT_CONNECTED_MESSAGE

    @pytest.mark.asyncio
    async def test_pipeline_failure_forwarded_to_client(self):
        """``code`` returns the pipeline's failure dict unchanged (Req 2.3, 11.7)."""
        ctx = _make_ctx()
        failure_result = {
            "status": "failed",
            "error": "clone failed: network error",
            "duration_seconds": 0.5,
        }

        with patch(
            "container.code_mcp_server.run_coding_pipeline",
            new_callable=AsyncMock,
            return_value=failure_result,
        ):
            result = await code(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="user-1",
                ctx=ctx,
            )

        assert result == failure_result
        assert result["status"] == "failed"
        assert "clone failed" in result["error"]
        assert len(result["error"]) <= 500

    @pytest.mark.asyncio
    async def test_validation_rejects_missing_user_id(self):
        """``code`` short-circuits with ``failed`` when ``_user_id`` is empty (Req 11.1).

        The pipeline must not be invoked in this case.
        """
        ctx = _make_ctx()

        with patch(
            "container.code_mcp_server.run_coding_pipeline",
            new_callable=AsyncMock,
        ) as mock_pipeline:
            result = await code(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                _user_id="",
                ctx=ctx,
            )

        assert result["status"] == "failed"
        assert "user_id" in result["error"]
        mock_pipeline.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_validation_rejects_out_of_range_timeout(self):
        """``code`` short-circuits on ``timeout_minutes`` out of [1, 30] (Req 11.1)."""
        ctx = _make_ctx()

        with patch(
            "container.code_mcp_server.run_coding_pipeline",
            new_callable=AsyncMock,
        ) as mock_pipeline:
            result = await code(
                task_description="task",
                repo_url="https://github.com/o/r",
                base_branch="main",
                timeout_minutes=0,
                _user_id="user-1",
                ctx=ctx,
            )

        assert result["status"] == "failed"
        assert "timeout_minutes" in result["error"]
        mock_pipeline.assert_not_awaited()
