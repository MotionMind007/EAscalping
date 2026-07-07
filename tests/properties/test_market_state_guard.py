"""
Property-based tests for MarketCollector state guard logic (Property 1).

Property 1: State Guard for Market Data Collection
  *For any* EA state, market data SHALL be collected only when the current
  state is NOT BOOT or CONNECT.

Feature: ea-gateway, Property 1: State Guard for Market Data Collection
**Validates: Requirements 1.1, 1.2**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.mirror.market_collector import (
    MarketCollector,
    EAState,
    TickData,
    CandleData,
    BLOCKED_STATES,
    ALLOWED_STATES,
    ALL_STATES,
)


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

all_states = st.sampled_from(ALL_STATES)
blocked_states = st.sampled_from(list(BLOCKED_STATES))
allowed_states = st.sampled_from(list(ALLOWED_STATES))

# Generate realistic tick data
tick_data = st.builds(
    TickData,
    timestamp=st.just("2024-01-15T10:30:00.123Z"),
    bid=st.floats(min_value=1800.0, max_value=2200.0, allow_nan=False, allow_infinity=False),
    ask=st.floats(min_value=1800.0, max_value=2200.0, allow_nan=False, allow_infinity=False),
    spread=st.integers(min_value=1, max_value=100),
)

# Generate realistic candle data
candle_data = st.builds(
    CandleData,
    timestamp=st.just("2024-01-15T10:30:00.000Z"),
    timeframe=st.sampled_from(["M1", "M5", "M15", "H1"]),
    open=st.floats(min_value=1800.0, max_value=2200.0, allow_nan=False, allow_infinity=False),
    high=st.floats(min_value=1800.0, max_value=2200.0, allow_nan=False, allow_infinity=False),
    low=st.floats(min_value=1800.0, max_value=2200.0, allow_nan=False, allow_infinity=False),
    close=st.floats(min_value=1800.0, max_value=2200.0, allow_nan=False, allow_infinity=False),
    volume=st.integers(min_value=0, max_value=100000),
)


# --------------------------------------------------------------------------
# Property Tests: State Guard for Market Data Collection
# --------------------------------------------------------------------------

class TestMarketStateGuard:
    """Property 1: State Guard for Market Data Collection."""

    @pytest.mark.property
    @given(state=all_states, tick=tick_data)
    def test_tick_collection_respects_state_guard(self, state, tick):
        """
        **Validates: Requirements 1.1, 1.2**

        For any EA state and any tick event:
        - If state is BOOT or CONNECT → tick SHALL NOT be collected
        - If state is any other state → tick SHALL be collected
        """
        collector = MarketCollector()
        collected = collector.on_tick(state, tick)

        if state in BLOCKED_STATES:
            assert collected is False
            assert len(collector.collected_ticks) == 0
        else:
            assert collected is True
            assert len(collector.collected_ticks) == 1

    @pytest.mark.property
    @given(state=all_states, candle=candle_data)
    def test_candle_collection_respects_state_guard(self, state, candle):
        """
        **Validates: Requirements 1.1, 1.2**

        For any EA state and any new bar event:
        - If state is BOOT or CONNECT → candle SHALL NOT be collected
        - If state is any other state → candle SHALL be collected
        """
        collector = MarketCollector()
        collected = collector.on_new_bar(state, candle)

        if state in BLOCKED_STATES:
            assert collected is False
            assert len(collector.collected_candles) == 0
        else:
            assert collected is True
            assert len(collector.collected_candles) == 1

    @pytest.mark.property
    @given(state=blocked_states, tick=tick_data)
    def test_blocked_states_never_collect_ticks(self, state, tick):
        """
        **Validates: Requirements 1.1, 1.2**

        For any state in {BOOT, CONNECT}, tick data SHALL NOT be collected.
        """
        collector = MarketCollector()
        collected = collector.on_tick(state, tick)

        assert collected is False
        assert collector.should_collect(state) is False

    @pytest.mark.property
    @given(state=blocked_states, candle=candle_data)
    def test_blocked_states_never_collect_candles(self, state, candle):
        """
        **Validates: Requirements 1.1, 1.2**

        For any state in {BOOT, CONNECT}, candle data SHALL NOT be collected.
        """
        collector = MarketCollector()
        collected = collector.on_new_bar(state, candle)

        assert collected is False
        assert collector.should_collect(state) is False

    @pytest.mark.property
    @given(state=allowed_states, tick=tick_data)
    def test_allowed_states_always_collect_ticks(self, state, tick):
        """
        **Validates: Requirements 1.1, 1.2**

        For any state after CONNECT, tick data SHALL be collected.
        """
        collector = MarketCollector()
        collected = collector.on_tick(state, tick)

        assert collected is True
        assert collector.should_collect(state) is True

    @pytest.mark.property
    @given(state=allowed_states, candle=candle_data)
    def test_allowed_states_always_collect_candles(self, state, candle):
        """
        **Validates: Requirements 1.1, 1.2**

        For any state after CONNECT, candle data SHALL be collected.
        """
        collector = MarketCollector()
        collected = collector.on_new_bar(state, candle)

        assert collected is True
        assert collector.should_collect(state) is True
