"""
Property-based tests for Tick Batching Logic (Property 3).

Property 3: Tick Batching Logic
  *For any* sequence of N ticks within time T:
  - if N/T > 10 ticks/sec → batch into groups of max 10
  - if N/T ≤ 10 ticks/sec → each tick sent individually (batch of 1)

Feature: ea-gateway, Property 3: Tick Batching Logic
**Validates: Requirements 1.6**
"""

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from tests.mirror.tick_batcher import Tick, TickBatch, TickBatcher


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Generate a high-rate tick sequence: many ticks in a short window
# N ticks in T seconds where N/T > 10
@st.composite
def high_rate_ticks(draw):
    """Generate tick sequences with rate > 10 ticks/sec."""
    # At least 2 ticks needed to compute rate
    n_ticks = draw(st.integers(min_value=2, max_value=100))

    # Time window such that n_ticks / time_window > 10
    # So time_window < n_ticks / 10
    max_window = (n_ticks / 10.0) - 0.001
    assume(max_window > 0)
    time_window = draw(st.floats(
        min_value=0.01,
        max_value=max(0.01, max_window),
        allow_nan=False,
        allow_infinity=False,
    ))

    # Ensure rate > 10
    rate = n_ticks / time_window
    assume(rate > 10)

    # Generate ticks evenly spaced across the window
    start_time = 1000.0
    ticks = []
    for i in range(n_ticks):
        t = start_time + (time_window * i / max(n_ticks - 1, 1))
        ticks.append(Tick(
            timestamp_sec=t,
            bid=2035.0 + i * 0.01,
            ask=2035.3 + i * 0.01,
            spread=30,
        ))

    return ticks


# Generate a low-rate tick sequence: few ticks in a long window
# N ticks in T seconds where N/T ≤ 10
@st.composite
def low_rate_ticks(draw):
    """Generate tick sequences with rate ≤ 10 ticks/sec."""
    # At least 2 ticks needed to compute rate
    n_ticks = draw(st.integers(min_value=2, max_value=50))

    # Time window such that n_ticks / time_window ≤ 10
    # Use a margin to avoid floating-point boundary issues (rate exactly 10.0)
    min_window = (n_ticks / 10.0) + 0.01
    time_window = draw(st.floats(
        min_value=min_window,
        max_value=min_window + 100.0,
        allow_nan=False,
        allow_infinity=False,
    ))

    # Ensure rate ≤ 10 (strictly, accounting for float precision)
    rate = n_ticks / time_window
    assume(rate <= 10)

    # Generate ticks evenly spaced across the window
    start_time = 1000.0
    ticks = []
    for i in range(n_ticks):
        t = start_time + (time_window * i / max(n_ticks - 1, 1))
        ticks.append(Tick(
            timestamp_sec=t,
            bid=2035.0 + i * 0.01,
            ask=2035.3 + i * 0.01,
            spread=30,
        ))

    return ticks


# Generate any tick sequence (for general invariant tests)
@st.composite
def any_tick_sequence(draw):
    """Generate arbitrary tick sequences."""
    n_ticks = draw(st.integers(min_value=1, max_value=100))
    time_window = draw(st.floats(
        min_value=0.1,
        max_value=60.0,
        allow_nan=False,
        allow_infinity=False,
    ))

    start_time = 1000.0
    ticks = []
    for i in range(n_ticks):
        t = start_time + (time_window * i / max(n_ticks - 1, 1))
        ticks.append(Tick(
            timestamp_sec=t,
            bid=2035.0 + i * 0.01,
            ask=2035.3 + i * 0.01,
            spread=30,
        ))

    return ticks


# --------------------------------------------------------------------------
# Property Tests: Tick Batching Logic
# --------------------------------------------------------------------------

class TestTickBatching:
    """Property 3: Tick Batching Logic."""

    @pytest.mark.property
    @given(ticks=high_rate_ticks())
    def test_high_rate_batches_max_10(self, ticks):
        """
        **Validates: Requirements 1.6**

        For any sequence of N ticks with rate > 10/sec,
        every batch SHALL have at most 10 ticks.
        """
        batcher = TickBatcher()
        batches = batcher.batch_ticks(ticks)

        assert len(batches) > 0
        for batch in batches:
            assert batch.size <= 10, (
                f"Batch size {batch.size} exceeds max of 10 for high-rate ticks"
            )

    @pytest.mark.property
    @given(ticks=low_rate_ticks())
    def test_low_rate_sends_individually(self, ticks):
        """
        **Validates: Requirements 1.6**

        For any sequence of N ticks with rate ≤ 10/sec,
        each tick SHALL be sent individually (batch size = 1).
        """
        batcher = TickBatcher()
        batches = batcher.batch_ticks(ticks)

        assert len(batches) == len(ticks)
        for batch in batches:
            assert batch.size == 1, (
                f"Batch size {batch.size} should be 1 for low-rate ticks"
            )

    @pytest.mark.property
    @given(ticks=any_tick_sequence())
    def test_all_ticks_preserved(self, ticks):
        """
        **Validates: Requirements 1.6**

        For any tick sequence, the total number of ticks across all
        batches SHALL equal the original number of input ticks (no data loss).
        """
        batcher = TickBatcher()
        batches = batcher.batch_ticks(ticks)

        total_ticks_in_batches = sum(batch.size for batch in batches)
        assert total_ticks_in_batches == len(ticks), (
            f"Expected {len(ticks)} ticks total, got {total_ticks_in_batches}"
        )

    @pytest.mark.property
    @given(ticks=any_tick_sequence())
    def test_batch_size_never_exceeds_10(self, ticks):
        """
        **Validates: Requirements 1.6**

        For any tick sequence regardless of rate, no single batch
        SHALL ever contain more than 10 ticks.
        """
        batcher = TickBatcher()
        batches = batcher.batch_ticks(ticks)

        for batch in batches:
            assert batch.size <= 10, (
                f"Batch size {batch.size} exceeds maximum of 10"
            )

    @pytest.mark.property
    @given(ticks=high_rate_ticks())
    def test_high_rate_order_preserved(self, ticks):
        """
        **Validates: Requirements 1.6**

        For any high-rate tick sequence, the order of ticks within
        and across batches SHALL match the original input order.
        """
        batcher = TickBatcher()
        batches = batcher.batch_ticks(ticks)

        # Flatten batches back and compare
        flattened = []
        for batch in batches:
            flattened.extend(batch.ticks)

        assert len(flattened) == len(ticks)
        for original, batched in zip(ticks, flattened):
            assert original.timestamp_sec == batched.timestamp_sec
            assert original.bid == batched.bid
