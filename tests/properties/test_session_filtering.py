"""
Property-based tests for Session-Based Command Filtering (Task 5.3 - Property 9).

Tests cover:
  - BUY/SELL commands rejected outside session window (H < 8 or H >= 21)
  - BUY/SELL commands accepted inside session window (8 <= H < 21)
  - CLOSE commands accepted regardless of session time

Feature: ea-gateway
Property 9: Session-Based Command Filtering

**Validates: Requirements 6.2, 6.3, 6.5**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.mirror.session_manager import SessionManager, TradeCommandType


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Full UTC hour range
utc_hours = st.integers(min_value=0, max_value=23)

# In-session hours: [8, 21)
in_session_hours = st.integers(min_value=8, max_value=20)

# Out-of-session hours: [0, 8) or [21, 23]
out_of_session_hours = st.one_of(
    st.integers(min_value=0, max_value=7),
    st.integers(min_value=21, max_value=23),
)

# Trade command types for open trades
open_trade_types = st.sampled_from([TradeCommandType.BUY, TradeCommandType.SELL])

# All trade command types
all_trade_types = st.sampled_from([
    TradeCommandType.BUY,
    TradeCommandType.SELL,
    TradeCommandType.CLOSE,
])


# --------------------------------------------------------------------------
# Property Tests: Session-Based Command Filtering (Property 9)
# --------------------------------------------------------------------------

class TestSessionCommandFiltering:
    """
    Property 9: Session-Based Command Filtering

    For any UTC time and any Trade_Command:
    - If the time is outside the session window (before 08:00 or at/after 21:00 UTC)
      and the command type is BUY or SELL, the command SHALL be rejected.
    - If the command type is CLOSE, the command SHALL be accepted regardless of
      session time.

    **Validates: Requirements 6.2, 6.3, 6.5**
    """

    @pytest.mark.property
    @given(
        cmd_type=open_trade_types,
        hour=out_of_session_hours,
    )
    def test_buy_sell_rejected_outside_session(self, cmd_type, hour):
        """
        **Validates: Requirements 6.2, 6.5**

        For any BUY or SELL command when UTC hour is outside [8, 21),
        the command SHALL be rejected with session error reason.
        """
        sm = SessionManager()
        accepted, reason = sm.filter_command(cmd_type, hour)

        assert accepted is False, (
            f"Expected {cmd_type.value} to be rejected at hour {hour}"
        )
        assert "outside session window" in reason

    @pytest.mark.property
    @given(
        cmd_type=open_trade_types,
        hour=in_session_hours,
    )
    def test_buy_sell_accepted_inside_session(self, cmd_type, hour):
        """
        **Validates: Requirements 6.2**

        For any BUY or SELL command when UTC hour is within [8, 21),
        the command SHALL be accepted (not session-rejected).
        """
        sm = SessionManager()
        accepted, reason = sm.filter_command(cmd_type, hour)

        assert accepted is True, (
            f"Expected {cmd_type.value} to be accepted at hour {hour}, "
            f"but got rejection: {reason}"
        )
        assert reason == ""

    @pytest.mark.property
    @given(hour=utc_hours)
    def test_close_always_accepted(self, hour):
        """
        **Validates: Requirements 6.5**

        For any CLOSE command at any UTC hour (0-23),
        the command SHALL always be accepted regardless of session time.
        """
        sm = SessionManager()
        accepted, reason = sm.filter_command(TradeCommandType.CLOSE, hour)

        assert accepted is True, (
            f"Expected CLOSE to be accepted at hour {hour}, "
            f"but got rejection: {reason}"
        )
        assert reason == ""

    @pytest.mark.property
    @given(
        cmd_type=all_trade_types,
        hour=utc_hours,
    )
    def test_command_filtering_complete(self, cmd_type, hour):
        """
        **Validates: Requirements 6.2, 6.3, 6.5**

        For any command type and any UTC hour, the filtering logic SHALL:
        - Accept CLOSE always
        - Accept BUY/SELL only if 8 <= H < 21
        - Reject BUY/SELL if H < 8 or H >= 21
        """
        sm = SessionManager()
        accepted, reason = sm.filter_command(cmd_type, hour)

        if cmd_type == TradeCommandType.CLOSE:
            # CLOSE always accepted
            assert accepted is True
            assert reason == ""
        elif cmd_type in (TradeCommandType.BUY, TradeCommandType.SELL):
            if 8 <= hour < 21:
                # In session: accepted
                assert accepted is True
                assert reason == ""
            else:
                # Outside session: rejected
                assert accepted is False
                assert "outside session window" in reason

    @pytest.mark.property
    @given(
        cmd_type=open_trade_types,
        hour=out_of_session_hours,
    )
    def test_market_data_continues_outside_session(self, cmd_type, hour):
        """
        **Validates: Requirements 6.3**

        Market data forwarding continues regardless of session time.
        Only BUY/SELL commands are filtered; the session manager does not
        affect data collection. This test confirms that can_close_trade()
        remains true (data/close operations are never session-blocked).
        """
        sm = SessionManager()

        # Close is never blocked (represents "data continues" indirectly)
        assert sm.can_close_trade() is True

        # But open trades are blocked outside session
        assert sm.can_open_trade(hour) is False
