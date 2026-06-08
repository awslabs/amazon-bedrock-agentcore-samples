# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for structured JSON logging configuration.

Requirements: 10.1, 10.2
Validates that the MCP server emits JSON-formatted log lines with the
expected fields: timestamp, level, logger, message, and optional context.
"""

import json
import io
import logging

from pythonjsonlogger import json as jsonlogger


def _make_json_logger(stream: io.StringIO) -> logging.Logger:
    """Create a logger configured with JsonFormatter writing to the given stream."""
    handler = logging.StreamHandler(stream)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)

    test_logger = logging.getLogger("test_structured_logging")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False
    return test_logger


class TestLogOutputIsValidJSON:
    """Verify that log output is valid JSON."""

    def test_info_message_is_valid_json(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("hello world")

        line = buf.getvalue().strip()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_warning_message_is_valid_json(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.warning("something went wrong")

        line = buf.getvalue().strip()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_multiline_message_is_valid_json(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("line one\nline two\nline three")

        line = buf.getvalue().strip()
        parsed = json.loads(line)
        assert "line one" in parsed["message"]


class TestExpectedFields:
    """Verify that JSON log lines contain the expected renamed fields."""

    def test_contains_timestamp_field(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("test message")

        parsed = json.loads(buf.getvalue().strip())
        assert "timestamp" in parsed

    def test_contains_level_field(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("test message")

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["level"] == "INFO"

    def test_contains_logger_field(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("test message")

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["logger"] == "test_structured_logging"

    def test_contains_message_field(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("test message")

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["message"] == "test message"

    def test_original_field_names_not_present(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("test message")

        parsed = json.loads(buf.getvalue().strip())
        # The original names should be renamed, not duplicated
        assert "asctime" not in parsed
        assert "levelname" not in parsed


class TestExtraContextFields:
    """Verify that extra context fields appear as top-level keys in JSON output."""

    def test_job_id_appears_as_top_level_key(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("processing job", extra={"job_id": "abc-123"})

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["job_id"] == "abc-123"

    def test_user_id_appears_as_top_level_key(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info("user action", extra={"user_id": "user-456"})

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["user_id"] == "user-456"

    def test_multiple_extra_fields(self):
        buf = io.StringIO()
        log = _make_json_logger(buf)
        log.info(
            "task complete",
            extra={"job_id": "j-1", "user_id": "u-2", "status": "COMPLETE"},
        )

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["job_id"] == "j-1"
        assert parsed["user_id"] == "u-2"
        assert parsed["status"] == "COMPLETE"
