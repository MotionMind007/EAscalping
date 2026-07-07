"""
Property-based tests for CommandDispatcher (Task 13.2).

Tests cover:
  - Trade command JSON parsing (type, lot_size, stop_loss, take_profit, ticket)
  - State response parsing (approved/rejected, new_state, embedded command)
  - Session-based command filtering (BUY/SELL rejected outside session, CLOSE always allowed)
  - Rejection report format

Feature: ea-gateway
"""

import json
import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from tests.mirror.command_dispatcher import (
    CommandDispatcher,
    SessionManager,
    TradeCommand,
    TradeCommandType,
    DispatchResult,
    StateResponse,
)


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

valid_command_types = st.sampled_from(["BUY", "SELL", "CLOSE"])
valid_lot_sizes = st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False)
valid_prices = st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
valid_tickets = st.integers(min_value=1, max_value=999999999)
utc_hours = st.integers(min_value=0, max_value=23)

# Session hours: [8, 21) are in-session
in_session_hours = st.integers(min_value=8, max_value=20)
out_of_session_hours = st.one_of(
    st.integers(min_value=0, max_value=7),
    st.integers(min_value=21, max_value=23),
)


def build_buy_sell_json(cmd_type: str, lot_size: float, sl: float, tp: float) -> str:
    """Build a valid BUY/SELL command JSON."""
    return json.dumps({
        "type": cmd_type,
        "lot_size": lot_size,
        "stop_loss": sl,
        "take_profit": tp,
    })


def build_close_json(ticket: int) -> str:
    """Build a valid CLOSE command JSON."""
    return json.dumps({
        "type": "CLOSE",
        "lot_size": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "ticket": ticket,
    })


# --------------------------------------------------------------------------
# Property Tests: Trade Command Parsing
# --------------------------------------------------------------------------

class TestParseTradeCommand:
    """Property tests for ParseTradeCommand."""

    @pytest.mark.property
    @given(
        cmd_type=st.sampled_from(["BUY", "SELL"]),
        lot_size=valid_lot_sizes,
        sl=valid_prices,
        tp=valid_prices,
    )
    def test_valid_buy_sell_always_parses(self, cmd_type, lot_size, sl, tp):
        """
        **Validates: Requirements 3.1, 3.2**

        For any valid BUY/SELL command JSON with lot_size > 0,
        parsing SHALL succeed and extract all fields correctly.
        """
        dispatcher = CommandDispatcher()
        json_body = build_buy_sell_json(cmd_type, lot_size, sl, tp)

        success, cmd = dispatcher.parse_trade_command(json_body)

        assert success is True
        assert cmd.type.value == cmd_type
        assert abs(cmd.lot_size - lot_size) < 1e-6
        assert abs(cmd.stop_loss - sl) < 1e-6
        assert abs(cmd.take_profit - tp) < 1e-6

    @pytest.mark.property
    @given(ticket=valid_tickets)
    def test_valid_close_always_parses(self, ticket):
        """
        **Validates: Requirements 3.3**

        For any valid CLOSE command JSON with ticket > 0,
        parsing SHALL succeed and extract ticket correctly.
        """
        dispatcher = CommandDispatcher()
        json_body = build_close_json(ticket)

        success, cmd = dispatcher.parse_trade_command(json_body)

        assert success is True
        assert cmd.type == TradeCommandType.CLOSE
        assert cmd.ticket == ticket

    @pytest.mark.property
    @given(
        cmd_type=st.sampled_from(["BUY", "SELL"]),
        lot_size=st.floats(min_value=-100.0, max_value=0.0, allow_nan=False, allow_infinity=False),
    )
    def test_invalid_lot_size_rejects(self, cmd_type, lot_size):
        """
        **Validates: Requirements 3.1, 3.2**

        For any BUY/SELL command with lot_size <= 0,
        parsing SHALL fail (return false).
        """
        dispatcher = CommandDispatcher()
        json_body = json.dumps({
            "type": cmd_type,
            "lot_size": lot_size,
            "stop_loss": 2030.0,
            "take_profit": 2045.0,
        })

        success, cmd = dispatcher.parse_trade_command(json_body)
        assert success is False

    @pytest.mark.property
    @given(invalid_type=st.text(min_size=1, max_size=20).filter(
        lambda x: x not in ("BUY", "SELL", "CLOSE")
    ))
    def test_unknown_type_rejects(self, invalid_type):
        """
        **Validates: Requirements 3.1, 3.2, 3.3**

        For any command JSON with unknown type string,
        parsing SHALL fail.
        """
        dispatcher = CommandDispatcher()
        json_body = json.dumps({
            "type": invalid_type,
            "lot_size": 0.1,
            "stop_loss": 2030.0,
            "take_profit": 2045.0,
        })

        success, cmd = dispatcher.parse_trade_command(json_body)
        assert success is False

    @pytest.mark.property
    @given(garbage=st.text(min_size=0, max_size=100).filter(
        lambda x: not x.strip().startswith("{")
    ))
    def test_invalid_json_rejects(self, garbage):
        """
        **Validates: Requirements 3.1, 3.2, 3.3**

        For any non-JSON input, parsing SHALL fail gracefully.
        """
        dispatcher = CommandDispatcher()
        success, cmd = dispatcher.parse_trade_command(garbage)
        assert success is False


# --------------------------------------------------------------------------
# Property Tests: State Response Parsing
# --------------------------------------------------------------------------

class TestParseStateResponse:
    """Property tests for ParseStateResponse."""

    @pytest.mark.property
    @given(
        approved=st.booleans(),
        new_state=st.sampled_from([
            "WAIT_SESSION", "CHECK_RISK", "SCAN_SIGNAL",
            "AI_CONFIRMATION", "OPEN_POSITION", "MANAGE_POSITION",
        ]),
    )
    def test_state_response_without_command(self, approved, new_state):
        """
        **Validates: Requirements 3.4, 3.5**

        For any state response with no embedded command,
        parsing SHALL extract approved and new_state correctly.
        """
        dispatcher = CommandDispatcher()
        json_body = json.dumps({
            "approved": approved,
            "new_state": new_state,
            "command": None,
        })

        success, resp = dispatcher.parse_state_response(json_body)

        assert success is True
        assert resp.approved == approved
        assert resp.new_state == new_state
        assert resp.has_command is False

    @pytest.mark.property
    @given(
        new_state=st.sampled_from(["OPEN_POSITION", "MANAGE_POSITION"]),
        lot_size=valid_lot_sizes,
        sl=valid_prices,
        tp=valid_prices,
    )
    def test_state_response_with_buy_command(self, new_state, lot_size, sl, tp):
        """
        **Validates: Requirements 3.4, 3.5**

        For any approved state response with an embedded BUY command,
        parsing SHALL extract both the state and the command correctly.
        """
        dispatcher = CommandDispatcher()
        json_body = json.dumps({
            "approved": True,
            "new_state": new_state,
            "command": {
                "type": "BUY",
                "lot_size": lot_size,
                "stop_loss": sl,
                "take_profit": tp,
            },
        })

        success, resp = dispatcher.parse_state_response(json_body)

        assert success is True
        assert resp.approved is True
        assert resp.new_state == new_state
        assert resp.has_command is True
        assert resp.command.type == TradeCommandType.BUY
        assert abs(resp.command.lot_size - lot_size) < 1e-6


# --------------------------------------------------------------------------
# Property Tests: Session-Based Command Filtering (Property 9)
# --------------------------------------------------------------------------

class TestSessionCommandFiltering:
    """Property tests for session-based command dispatch filtering."""

    @pytest.mark.property
    @given(
        cmd_type=st.sampled_from([TradeCommandType.BUY, TradeCommandType.SELL]),
        utc_hour=out_of_session_hours,
        lot_size=valid_lot_sizes,
    )
    def test_buy_sell_rejected_outside_session(self, cmd_type, utc_hour, lot_size):
        """
        **Validates: Requirements 6.2, 6.5**

        For any BUY or SELL command when UTC hour is outside [8, 21),
        the command SHALL be rejected with session error.
        """
        dispatcher = CommandDispatcher()
        cmd = TradeCommand(
            type=cmd_type,
            lot_size=lot_size,
            stop_loss=2030.0,
            take_profit=2045.0,
        )

        result = dispatcher.dispatch_command(cmd, utc_hour)

        assert result.dispatched is False
        assert result.rejected_session is True
        assert result.rejection_report is not None
        assert result.rejection_report["success"] is False
        assert result.rejection_report["error_code"] == -2
        assert "outside session window" in result.rejection_report["error_message"]
        assert result.rejection_report["command_type"] == cmd_type.value

    @pytest.mark.property
    @given(
        cmd_type=st.sampled_from([TradeCommandType.BUY, TradeCommandType.SELL]),
        utc_hour=in_session_hours,
        lot_size=valid_lot_sizes,
    )
    def test_buy_sell_allowed_in_session(self, cmd_type, utc_hour, lot_size):
        """
        **Validates: Requirements 3.1, 3.2, 6.2**

        For any BUY or SELL command when UTC hour is within [8, 21),
        the command SHALL be dispatched (not session-rejected).
        """
        dispatcher = CommandDispatcher()
        cmd = TradeCommand(
            type=cmd_type,
            lot_size=lot_size,
            stop_loss=2030.0,
            take_profit=2045.0,
        )

        result = dispatcher.dispatch_command(cmd, utc_hour)

        assert result.dispatched is True
        assert result.rejected_session is False

    @pytest.mark.property
    @given(
        utc_hour=utc_hours,
        ticket=valid_tickets,
    )
    def test_close_always_allowed(self, utc_hour, ticket):
        """
        **Validates: Requirements 6.5**

        For any CLOSE command at any UTC hour (in or out of session),
        the command SHALL always be dispatched (never session-rejected).
        """
        dispatcher = CommandDispatcher()
        cmd = TradeCommand(
            type=TradeCommandType.CLOSE,
            lot_size=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            ticket=ticket,
        )

        result = dispatcher.dispatch_command(cmd, utc_hour)

        assert result.dispatched is True
        assert result.rejected_session is False
