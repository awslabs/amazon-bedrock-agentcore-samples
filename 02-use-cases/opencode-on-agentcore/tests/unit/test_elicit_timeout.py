# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit test for _elicit_with_timeout helper.

Validates that the helper returns None when ctx.elicit() blocks
beyond ELICITATION_TIMEOUT_S.

Requirements: 2.5
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from container.code_mcp_server import _elicit_with_timeout


@pytest.mark.asyncio
async def test_elicit_with_timeout_returns_none_on_timeout():
    """Mock ctx.elicit to block indefinitely; assert helper returns None."""
    never_done = asyncio.Event()

    ctx = MagicMock()
    ctx.elicit = MagicMock(return_value=never_done.wait())

    with patch("container.code_mcp_server.ELICITATION_TIMEOUT_S", 0.1):
        result = await _elicit_with_timeout(
            ctx,
            message="test prompt",
            schema={"type": "object", "properties": {}},
        )

    assert result is None


@pytest.mark.asyncio
async def test_elicit_with_timeout_returns_result_on_success():
    """When ctx.elicit resolves normally, the helper returns its result."""
    expected = MagicMock(action="submit", data={"confirmation": "done"})
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=expected)

    with patch("container.code_mcp_server.ELICITATION_TIMEOUT_S", 5):
        result = await _elicit_with_timeout(
            ctx,
            message="test prompt",
            schema={"type": "object", "properties": {}},
        )

    assert result is expected
