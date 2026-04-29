# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for run_opencode_acp tool."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from container.tools.run_opencode_acp import (
    OpenCodeResult,
    _build_opencode_config,
    _build_spawn_env,
    _make_jsonrpc,
    run_opencode_acp_impl,
)


class TestMakeJsonrpc:
    def test_basic_message(self):
        result = _make_jsonrpc(1, "initialize", {"protocolVersion": "1.0"})
        parsed = json.loads(result)
        assert parsed == {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "1.0"},
        }

    def test_ends_with_newline(self):
        result = _make_jsonrpc(1, "test", {})
        assert result.endswith("\n")


class TestBuildOpenCodeConfig:
    def test_shape(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_MODEL", "global.anthropic.claude-opus-4-6-v1")
        config = _build_opencode_config()
        assert config["model"] == "amazon-bedrock/global.anthropic.claude-opus-4-6-v1"
        assert config["autoupdate"] is False
        assert "opencode" in config["disabled_providers"]
        assert config["permission"]["edit"] == "allow"
        assert config["permission"]["bash"] == "allow"

    def test_default_model(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        config = _build_opencode_config()
        assert config["model"] == (
            "amazon-bedrock/global.anthropic.claude-opus-4-6-v1"
        )


class TestBuildSpawnEnv:
    def test_sets_autoupdate_disable_flag(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPENCODE_MODEL", raising=False)
        env = _build_spawn_env(str(tmp_path))
        # AUTOUPDATE is the only DISABLE_* flag that has been proven
        # necessary — the microVM has a fresh filesystem on every cold
        # start and autoupdate would attempt to download a new OpenCode
        # binary each time.
        assert env["OPENCODE_DISABLE_AUTOUPDATE"] == "true"

    def test_config_file_written(self, tmp_path):
        """_write_opencode_config writes opencode.json to work_dir."""
        import importlib
        mod = importlib.import_module("container.tools.run_opencode_acp")
        mod._write_opencode_config(str(tmp_path))
        config_path = tmp_path / "opencode.json"
        assert config_path.exists()
        config = json.loads(config_path.read_text())
        assert config["model"].startswith("amazon-bedrock/")
        assert config.get("autoupdate") is False

    def test_aws_creds_passed_through(self, tmp_path, monkeypatch):
        """AWS creds resolved from boto3 are set on the spawn env."""
        import importlib
        mod = importlib.import_module("container.tools.run_opencode_acp")

        def _fake_resolve():
            return {
                "AWS_ACCESS_KEY_ID": "AKIA-FAKE",
                "AWS_SECRET_ACCESS_KEY": "FAKE-SECRET",
                "AWS_SESSION_TOKEN": "FAKE-SESSION-TOKEN",
            }

        monkeypatch.setattr(mod, "_resolve_aws_credentials_into_env", _fake_resolve)
        env = _build_spawn_env(str(tmp_path))
        assert env["AWS_ACCESS_KEY_ID"] == "AKIA-FAKE"
        assert env["AWS_SECRET_ACCESS_KEY"] == "FAKE-SECRET"
        assert env["AWS_SESSION_TOKEN"] == "FAKE-SESSION-TOKEN"


def _make_acp_response(id: int, result: dict) -> bytes:
    """Helper to create a JSON-RPC response line."""
    return (json.dumps({"jsonrpc": "2.0", "id": id, "result": result}) + "\n").encode()


def _make_acp_notification(method: str, params: dict) -> bytes:
    """Helper to create a JSON-RPC notification line."""
    return (json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n").encode()


def _mock_proc(stdout_lines: list[bytes], returncode: int = 0, stderr: bytes = b""):
    """Create a mock async subprocess with given stdout lines.

    Note: ``returncode`` sets the value on the mock immediately (as if the
    process has already exited). Callers that want to exercise the
    "process alive while reading" path should leave it at the default 0
    and rely on stdout EOF to trigger the loop exit.
    """
    proc = AsyncMock()
    proc.returncode = returncode
    proc.stdin = AsyncMock()
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.stdout = asyncio.StreamReader()
    proc.stdout.feed_data(b"".join(stdout_lines))
    proc.stdout.feed_eof()
    proc.stderr = asyncio.StreamReader()
    proc.stderr.feed_data(stderr)
    proc.stderr.feed_eof()
    proc.send_signal = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=returncode)
    return proc


class TestRunOpenCodeAcp:
    """Tests for the run_opencode_acp_impl function."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, tmp_path):
        """Test a successful ACP protocol exchange."""
        proc = _mock_proc([
            _make_acp_response(1, {"protocolVersion": "1.0"}),
            _make_acp_response(2, {"sessionId": "sess-123"}),
            _make_acp_notification("session/update", {
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"text": "Editing file.py"},
                },
            }),
            _make_acp_notification("session/update", {
                "update": {
                    "sessionUpdate": "tool_call",
                    "title": "Edit file.py",
                    "locations": [{"uri": "file.py"}],
                },
            }),
            _make_acp_response(3, {"stopReason": "end_turn"}),
        ])

        progress_messages = []

        with patch("container.tools.run_opencode_acp.asyncio.create_subprocess_exec",
                    return_value=proc):
            result = await run_opencode_acp_impl(
                work_dir=str(tmp_path),
                task_description="Fix the bug",
                timeout_seconds=60,
                on_progress=lambda msg: progress_messages.append(msg),
            )

        assert result["stop_reason"] == "end_turn"
        assert "Editing file.py" in result["stdout"]
        assert result["files_edited"] == ["file.py"]
        assert "Editing file.py" in progress_messages
        assert "Edit file.py" in progress_messages

    @pytest.mark.asyncio
    async def test_acp_error_response(self, tmp_path):
        """Test handling of an ACP error response."""
        error_line = (json.dumps({
            "jsonrpc": "2.0", "id": 3,
            "error": {"code": -1, "message": "Model overloaded"},
        }) + "\n").encode()

        proc = _mock_proc([
            _make_acp_response(1, {"protocolVersion": "1.0"}),
            _make_acp_response(2, {"sessionId": "sess-456"}),
            error_line,
        ], returncode=1, stderr=b"error output")

        with patch("container.tools.run_opencode_acp.asyncio.create_subprocess_exec",
                    return_value=proc):
            with pytest.raises(RuntimeError, match="Model overloaded"):
                await run_opencode_acp_impl(
                    work_dir=str(tmp_path),
                    task_description="Fix the bug",
                    timeout_seconds=60,
                )

    @pytest.mark.asyncio
    async def test_no_session_id_raises(self, tmp_path):
        """Test that missing sessionId raises RuntimeError."""
        proc = _mock_proc([
            _make_acp_response(1, {"protocolVersion": "1.0"}),
            _make_acp_response(2, {}),  # No sessionId
        ], returncode=1)

        with patch("container.tools.run_opencode_acp.asyncio.create_subprocess_exec",
                    return_value=proc):
            with pytest.raises(RuntimeError, match="No sessionId"):
                await run_opencode_acp_impl(
                    work_dir=str(tmp_path),
                    task_description="Fix the bug",
                    timeout_seconds=60,
                )

    @pytest.mark.asyncio
    async def test_multiple_progress_notifications(self, tmp_path):
        """Test that multiple session/update notifications are forwarded."""
        proc = _mock_proc([
            _make_acp_response(1, {"protocolVersion": "1.0"}),
            _make_acp_response(2, {"sessionId": "sess-789"}),
            _make_acp_notification("session/update", {
                "update": {"sessionUpdate": "agent_message_chunk", "content": {"text": "Reading main.py"}},
            }),
            _make_acp_notification("session/update", {
                "update": {"sessionUpdate": "agent_message_chunk", "content": {"text": "Editing utils.py"}},
            }),
            _make_acp_notification("session/update", {
                "update": {"sessionUpdate": "agent_message_chunk", "content": {"text": "Running tests"}},
            }),
            _make_acp_response(3, {"stopReason": "end_turn"}),
        ])

        progress_messages = []

        with patch("container.tools.run_opencode_acp.asyncio.create_subprocess_exec",
                    return_value=proc):
            result = await run_opencode_acp_impl(
                work_dir=str(tmp_path),
                task_description="Refactor code",
                timeout_seconds=120,
                on_progress=lambda msg: progress_messages.append(msg),
            )

        assert progress_messages == ["Reading main.py", "Editing utils.py", "Running tests"]
        assert result["stop_reason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_positive_nonzero_exit_code_raises(self, tmp_path):
        """Positive non-zero exit codes still indicate a real failure.

        Negative codes (signals, e.g. -15 from our own SIGTERM cleanup)
        are tolerated — see ``test_negative_exit_code_tolerated``.
        """
        proc = _mock_proc([
            _make_acp_response(1, {"protocolVersion": "1.0"}),
            _make_acp_response(2, {"sessionId": "s1"}),
            _make_acp_response(3, {"stopReason": "end_turn"}),
        ], returncode=137, stderr=b"killed by OOM")

        with patch("container.tools.run_opencode_acp.asyncio.create_subprocess_exec",
                    return_value=proc):
            with pytest.raises(RuntimeError, match="exited with code 137"):
                await run_opencode_acp_impl(
                    work_dir=str(tmp_path),
                    task_description="Fix bug",
                    timeout_seconds=60,
                )

    @pytest.mark.asyncio
    async def test_negative_exit_code_tolerated(self, tmp_path):
        """A negative return code (our own SIGTERM) must not fail the run.

        After we read the final ``stopReason`` and break out of the loop,
        the ``finally`` block terminates the still-running process. The
        resulting -15 return code is expected cleanup, not a failure.
        """
        proc = _mock_proc([
            _make_acp_response(1, {"protocolVersion": "1.0"}),
            _make_acp_response(2, {"sessionId": "s1"}),
            _make_acp_response(3, {"stopReason": "end_turn"}),
        ], returncode=-15)

        with patch("container.tools.run_opencode_acp.asyncio.create_subprocess_exec",
                    return_value=proc):
            result = await run_opencode_acp_impl(
                work_dir=str(tmp_path),
                task_description="Fix bug",
                timeout_seconds=60,
            )

        assert result["stop_reason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_no_progress_callback(self, tmp_path):
        """Test that on_progress=None doesn't cause errors."""
        proc = _mock_proc([
            _make_acp_response(1, {"protocolVersion": "1.0"}),
            _make_acp_response(2, {"sessionId": "sess-abc"}),
            _make_acp_notification("session/update", {
                "update": {"sessionUpdate": "agent_message_chunk", "content": {"text": "Working..."}},
            }),
            _make_acp_response(3, {"stopReason": "end_turn"}),
        ])

        with patch("container.tools.run_opencode_acp.asyncio.create_subprocess_exec",
                    return_value=proc):
            result = await run_opencode_acp_impl(
                work_dir=str(tmp_path),
                task_description="Fix bug",
                timeout_seconds=60,
                on_progress=None,
            )

        assert result["stop_reason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_eof_before_init_response(self, tmp_path):
        """Test that EOF before initialize response raises RuntimeError."""
        proc = _mock_proc([], returncode=1)

        with patch("container.tools.run_opencode_acp.asyncio.create_subprocess_exec",
                    return_value=proc):
            with pytest.raises(RuntimeError, match="closed stdout before initialize"):
                await run_opencode_acp_impl(
                    work_dir=str(tmp_path),
                    task_description="Fix bug",
                    timeout_seconds=60,
                )
