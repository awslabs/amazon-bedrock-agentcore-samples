# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: OpenTelemetry instrument caching idempotence.

**Validates: Requirements 6.2, 6.3, 6.4**

Property 8 — Instrument caching idempotence:
  For any sequence of record_metric (or record_histogram) calls,
  create_counter (or create_histogram) SHALL be called exactly once
  per unique instrument name, regardless of how many times that name
  appears in the sequence.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

import container.lib.metrics as metrics_module

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Metric names: non-empty printable strings (realistic instrument names)
_metric_name = st.text(
    alphabet=st.sampled_from(list("abcdefghijklmnopqrstuvwxyz_.-0123456789")),
    min_size=1,
    max_size=30,
)

# A sequence of metric names (with duplicates) — at least 1 call
_metric_name_sequence = st.lists(_metric_name, min_size=1, max_size=50)


# ---------------------------------------------------------------------------
# Property 8a: create_counter called exactly once per unique name
# ---------------------------------------------------------------------------


class TestCounterCachingProperty:
    """**Validates: Requirements 6.2, 6.4**"""

    @given(names=_metric_name_sequence)
    @settings(max_examples=100, deadline=5_000)
    def test_create_counter_called_once_per_unique_name(self, names):
        """For any sequence of metric names, create_counter is called
        exactly once per unique name."""
        # Clear caches between runs
        metrics_module._counters.clear()

        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_meter.create_counter.return_value = mock_counter

        with patch.object(metrics_module, "_meter", mock_meter):
            for name in names:
                metrics_module.record_metric(name, 1.0)

        unique_names = set(names)

        # create_counter called exactly once per unique name
        assert mock_meter.create_counter.call_count == len(unique_names)

        # Verify each unique name was passed exactly once
        called_names = [
            call.args[0] for call in mock_meter.create_counter.call_args_list
        ]
        assert set(called_names) == unique_names
        assert len(called_names) == len(unique_names)


# ---------------------------------------------------------------------------
# Property 8b: create_histogram called exactly once per unique name
# ---------------------------------------------------------------------------


class TestHistogramCachingProperty:
    """**Validates: Requirements 6.3, 6.4**"""

    @given(names=_metric_name_sequence)
    @settings(max_examples=100, deadline=5_000)
    def test_create_histogram_called_once_per_unique_name(self, names):
        """For any sequence of metric names, create_histogram is called
        exactly once per unique name."""
        # Clear caches between runs
        metrics_module._histograms.clear()

        mock_meter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_histogram.return_value = mock_histogram

        with patch.object(metrics_module, "_meter", mock_meter):
            for name in names:
                metrics_module.record_histogram(name, 1.0, unit="ms")

        unique_names = set(names)

        # create_histogram called exactly once per unique name
        assert mock_meter.create_histogram.call_count == len(unique_names)

        # Verify each unique name was passed exactly once
        called_names = [
            call.args[0] for call in mock_meter.create_histogram.call_args_list
        ]
        assert set(called_names) == unique_names
        assert len(called_names) == len(unique_names)
