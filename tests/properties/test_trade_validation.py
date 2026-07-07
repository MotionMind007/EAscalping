"""
Property-based tests for TradeExecutor validation logic (Property 7).

Property 7: Trade Command Validation
For any Trade_Command of type BUY or SELL, the command SHALL be accepted only if:
  1. lot size is within [0.01, 100.0]
  2. stop-loss and take-profit are valid price levels
  3. no position is currently open on XAUUSD

If any condition fails, the command SHALL be rejected with the appropriate reason.

Feature: ea-gateway, Property 7: Trade Command Validation
"""

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from tests.mirror.trade_executor import (
    TradeExecutor,
    TradeCommand,
    TradeCommandType,
    TRADE_LOT_MIN,
    TRADE_LOT_MAX,
)


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Lot sizes spanning valid and invalid ranges
lot_sizes_full_range = st.floats(
    min_value=0.001, max_value=200.0, allow_nan=False, allow_infinity=False
)
valid_lot_sizes = st.floats(
    min_value=TRADE_LOT_MIN, max_value=TRADE_LOT_MAX, allow_nan=False, allow_infinity=False
)
invalid_lot_sizes_low = st.floats(
    min_value=0.001, max_value=0.0099, allow_nan=False, allow_infinity=False
)
invalid_lot_sizes_high = st.floats(
    min_value=100.01, max_value=200.0, allow_nan=False, allow_infinity=False
)

# Prices for SL/TP generation
current_prices = st.floats(
    min_value=1500.0, max_value=2500.0, allow_nan=False, allow_infinity=False
)

# SL/TP values including 0 (not set)
sl_tp_values = st.floats(
    min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False
)

# Position states
has_position = st.booleans()
open_tickets = st.integers(min_value=1, max_value=999999999)

# Command types for BUY/SELL
buy_sell_types = st.sampled_from([TradeCommandType.BUY, TradeCommandType.SELL])


# --------------------------------------------------------------------------
# Helper: Build valid SL/TP for a given direction and price
# --------------------------------------------------------------------------

def valid_sl_for_buy(price: float) -> st.SearchStrategy:
    """Generate SL below price (or 0 for no SL)."""
    return st.one_of(
        st.just(0.0),
        st.floats(min_value=1.0, max_value=price - 0.01, allow_nan=False, allow_infinity=False),
    )


def valid_tp_for_buy(price: float) -> st.SearchStrategy:
    """Generate TP above price (or 0 for no TP)."""
    return st.one_of(
        st.just(0.0),
        st.floats(min_value=price + 0.01, max_value=5000.0, allow_nan=False, allow_infinity=False),
    )


def valid_sl_for_sell(price: float) -> st.SearchStrategy:
    """Generate SL above price (or 0 for no SL)."""
    return st.one_of(
        st.just(0.0),
        st.floats(min_value=price + 0.01, max_value=5000.0, allow_nan=False, allow_infinity=False),
    )


def valid_tp_for_sell(price: float) -> st.SearchStrategy:
    """Generate TP below price (or 0 for no TP)."""
    return st.one_of(
        st.just(0.0),
        st.floats(min_value=1.0, max_value=price - 0.01, allow_nan=False, allow_infinity=False),
    )


# --------------------------------------------------------------------------
# Property Tests: Trade Command Validation (Property 7)
# --------------------------------------------------------------------------

class TestTradeCommandValidation:
    """
    Property 7: Trade Command Validation

    **Validates: Requirements 3.1, 3.2, 3.6**
    """

    # ------------------------------------------------------------------
    # Acceptance: all conditions met → command accepted
    # ------------------------------------------------------------------

    @pytest.mark.property
    @given(
        cmd_type=buy_sell_types,
        lot_size=valid_lot_sizes,
        current_price=current_prices,
        data=st.data(),
    )
    def test_valid_command_accepted(self, cmd_type, lot_size, current_price, data):
        """
        **Validates: Requirements 3.1, 3.2**

        For any BUY/SELL command with valid lot size, valid SL/TP, and no
        open position, the command SHALL be accepted.
        """
        # Generate valid SL/TP based on direction
        if cmd_type == TradeCommandType.BUY:
            sl = data.draw(valid_sl_for_buy(current_price))
            tp = data.draw(valid_tp_for_buy(current_price))
        else:
            sl = data.draw(valid_sl_for_sell(current_price))
            tp = data.draw(valid_tp_for_sell(current_price))

        executor = TradeExecutor(
            has_open_position=False,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=cmd_type,
            lot_size=lot_size,
            stop_loss=sl,
            take_profit=tp,
        )

        result = executor.validate_command(cmd)

        assert result.valid is True
        assert result.error_reason == ""

    # ------------------------------------------------------------------
    # Rejection: lot size out of range
    # ------------------------------------------------------------------

    @pytest.mark.property
    @given(
        cmd_type=buy_sell_types,
        lot_size=invalid_lot_sizes_low,
        current_price=current_prices,
    )
    def test_lot_size_too_small_rejected(self, cmd_type, lot_size, current_price):
        """
        **Validates: Requirements 3.1, 3.2**

        For any BUY/SELL command with lot size < 0.01,
        the command SHALL be rejected with lot size error.
        """
        executor = TradeExecutor(
            has_open_position=False,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=cmd_type,
            lot_size=lot_size,
            stop_loss=0.0,
            take_profit=0.0,
        )

        result = executor.validate_command(cmd)

        assert result.valid is False
        assert "lot size" in result.error_reason.lower()

    @pytest.mark.property
    @given(
        cmd_type=buy_sell_types,
        lot_size=invalid_lot_sizes_high,
        current_price=current_prices,
    )
    def test_lot_size_too_large_rejected(self, cmd_type, lot_size, current_price):
        """
        **Validates: Requirements 3.1, 3.2**

        For any BUY/SELL command with lot size > 100.0,
        the command SHALL be rejected with lot size error.
        """
        executor = TradeExecutor(
            has_open_position=False,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=cmd_type,
            lot_size=lot_size,
            stop_loss=0.0,
            take_profit=0.0,
        )

        result = executor.validate_command(cmd)

        assert result.valid is False
        assert "lot size" in result.error_reason.lower()

    # ------------------------------------------------------------------
    # Rejection: open position exists
    # ------------------------------------------------------------------

    @pytest.mark.property
    @given(
        cmd_type=buy_sell_types,
        lot_size=valid_lot_sizes,
        current_price=current_prices,
        open_ticket=open_tickets,
    )
    def test_open_position_rejects_buy_sell(self, cmd_type, lot_size, current_price, open_ticket):
        """
        **Validates: Requirements 3.6**

        For any BUY/SELL command when a position is already open,
        the command SHALL be rejected with position error.
        """
        executor = TradeExecutor(
            has_open_position=True,
            open_ticket=open_ticket,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=cmd_type,
            lot_size=lot_size,
            stop_loss=0.0,
            take_profit=0.0,
        )

        result = executor.validate_command(cmd)

        assert result.valid is False
        assert "position already open" in result.error_reason.lower()

    # ------------------------------------------------------------------
    # Rejection: invalid SL/TP for BUY
    # ------------------------------------------------------------------

    @pytest.mark.property
    @given(
        lot_size=valid_lot_sizes,
        current_price=current_prices,
        data=st.data(),
    )
    def test_buy_sl_above_price_rejected(self, lot_size, current_price, data):
        """
        **Validates: Requirements 3.1**

        For a BUY command, if SL >= current_price (non-zero),
        the command SHALL be rejected with SL error.
        """
        # Generate SL at or above current price
        sl = data.draw(st.floats(
            min_value=current_price,
            max_value=current_price + 500.0,
            allow_nan=False,
            allow_infinity=False,
        ))

        executor = TradeExecutor(
            has_open_position=False,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=TradeCommandType.BUY,
            lot_size=lot_size,
            stop_loss=sl,
            take_profit=0.0,
        )

        result = executor.validate_command(cmd)

        assert result.valid is False
        assert "sl" in result.error_reason.lower()

    @pytest.mark.property
    @given(
        lot_size=valid_lot_sizes,
        current_price=current_prices,
        data=st.data(),
    )
    def test_buy_tp_below_price_rejected(self, lot_size, current_price, data):
        """
        **Validates: Requirements 3.1**

        For a BUY command, if TP <= current_price (non-zero),
        the command SHALL be rejected with TP error.
        """
        # Generate TP at or below current price (but > 0)
        tp = data.draw(st.floats(
            min_value=0.01,
            max_value=current_price,
            allow_nan=False,
            allow_infinity=False,
        ))

        executor = TradeExecutor(
            has_open_position=False,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=TradeCommandType.BUY,
            lot_size=lot_size,
            stop_loss=0.0,
            take_profit=tp,
        )

        result = executor.validate_command(cmd)

        assert result.valid is False
        assert "tp" in result.error_reason.lower()

    # ------------------------------------------------------------------
    # Rejection: invalid SL/TP for SELL
    # ------------------------------------------------------------------

    @pytest.mark.property
    @given(
        lot_size=valid_lot_sizes,
        current_price=current_prices,
        data=st.data(),
    )
    def test_sell_sl_below_price_rejected(self, lot_size, current_price, data):
        """
        **Validates: Requirements 3.2**

        For a SELL command, if SL <= current_price (non-zero),
        the command SHALL be rejected with SL error.
        """
        # Generate SL at or below current price (but > 0)
        sl = data.draw(st.floats(
            min_value=0.01,
            max_value=current_price,
            allow_nan=False,
            allow_infinity=False,
        ))

        executor = TradeExecutor(
            has_open_position=False,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=TradeCommandType.SELL,
            lot_size=lot_size,
            stop_loss=sl,
            take_profit=0.0,
        )

        result = executor.validate_command(cmd)

        assert result.valid is False
        assert "sl" in result.error_reason.lower()

    @pytest.mark.property
    @given(
        lot_size=valid_lot_sizes,
        current_price=current_prices,
        data=st.data(),
    )
    def test_sell_tp_above_price_rejected(self, lot_size, current_price, data):
        """
        **Validates: Requirements 3.2**

        For a SELL command, if TP >= current_price (non-zero),
        the command SHALL be rejected with TP error.
        """
        # Generate TP at or above current price
        tp = data.draw(st.floats(
            min_value=current_price,
            max_value=current_price + 500.0,
            allow_nan=False,
            allow_infinity=False,
        ))

        executor = TradeExecutor(
            has_open_position=False,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=TradeCommandType.SELL,
            lot_size=lot_size,
            stop_loss=0.0,
            take_profit=tp,
        )

        result = executor.validate_command(cmd)

        assert result.valid is False
        assert "tp" in result.error_reason.lower()

    # ------------------------------------------------------------------
    # Combined: random lot + random SL/TP + random position state
    # ------------------------------------------------------------------

    @pytest.mark.property
    @given(
        cmd_type=buy_sell_types,
        lot_size=lot_sizes_full_range,
        sl=sl_tp_values,
        tp=sl_tp_values,
        current_price=current_prices,
        has_position=has_position,
        open_ticket=open_tickets,
    )
    def test_acceptance_iff_all_conditions_met(
        self, cmd_type, lot_size, sl, tp, current_price, has_position, open_ticket
    ):
        """
        **Validates: Requirements 3.1, 3.2, 3.6**

        For any BUY/SELL command with random parameters:
        - Accepted IFF lot in [0.01, 100.0] AND valid SL/TP AND no open position
        - Rejected otherwise with appropriate reason
        """
        executor = TradeExecutor(
            has_open_position=has_position,
            open_ticket=open_ticket,
            current_price=current_price,
        )
        cmd = TradeCommand(
            type=cmd_type,
            lot_size=lot_size,
            stop_loss=sl,
            take_profit=tp,
        )

        result = executor.validate_command(cmd)

        # Compute expected validity
        lot_valid = TRADE_LOT_MIN <= lot_size <= TRADE_LOT_MAX
        position_valid = not has_position

        # SL/TP validity
        sl_valid = True
        tp_valid = True

        if sl < 0:
            sl_valid = False
        elif sl != 0.0:
            if cmd_type == TradeCommandType.BUY:
                sl_valid = sl < current_price
            else:
                sl_valid = sl > current_price

        if tp < 0:
            tp_valid = False
        elif tp != 0.0:
            if cmd_type == TradeCommandType.BUY:
                tp_valid = tp > current_price
            else:
                tp_valid = tp < current_price

        sl_tp_valid = sl_valid and tp_valid
        expected_valid = lot_valid and sl_tp_valid and position_valid

        assert result.valid == expected_valid

        if not result.valid:
            # Must have an error reason
            assert result.error_reason != ""

            # Verify the rejection reason matches the FIRST failed condition
            # (validation checks lot → SL/TP → position, in order)
            if not lot_valid:
                assert "lot size" in result.error_reason.lower()
            elif not sl_tp_valid:
                assert "sl" in result.error_reason.lower() or "tp" in result.error_reason.lower()
            elif not position_valid:
                assert "position" in result.error_reason.lower()
