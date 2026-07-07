"""
Python mirror implementation of CTradeExecutor (Include/EAGateway/TradeExecutor.mqh).

This module provides the same validation logic as the MQL5 implementation
for property-based testing. It mirrors:
  - Lot size validation: [0.01, 100.0]
  - SL/TP validation relative to current price and command direction
  - Position state check: no open position for BUY/SELL
  - CLOSE ticket validation

Feature: ea-gateway
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


# --------------------------------------------------------------------------
# Constants matching TradeExecutor.mqh
# --------------------------------------------------------------------------

TRADE_LOT_MIN = 0.01
TRADE_LOT_MAX = 100.0


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class TradeCommandType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class TradeCommand:
    type: TradeCommandType = TradeCommandType.BUY
    lot_size: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    ticket: int = 0


@dataclass
class ValidationResult:
    valid: bool = False
    error_reason: str = ""


# --------------------------------------------------------------------------
# TradeExecutor mirror
# --------------------------------------------------------------------------

class TradeExecutor:
    """
    Python mirror of CTradeExecutor validation logic.

    Models trade command validation without actual MT5 execution.
    Validates:
      - Lot size within [0.01, 100.0]
      - SL/TP price levels relative to current market price
      - No existing open position for BUY/SELL commands
      - Ticket match for CLOSE commands
    """

    def __init__(
        self,
        has_open_position: bool = False,
        open_ticket: int = 0,
        current_price: float = 2000.0,
    ):
        self._has_open_position = has_open_position
        self._open_ticket = open_ticket
        self._current_price = current_price

    @property
    def has_open_position(self) -> bool:
        return self._has_open_position

    @property
    def open_ticket(self) -> int:
        return self._open_ticket

    def validate_command(self, cmd: TradeCommand) -> ValidationResult:
        """
        Validate a trade command.

        For BUY/SELL:
          1. Lot size must be in [0.01, 100.0]
          2. SL/TP must be valid price levels (0 means not set)
             - BUY: SL < current_price (if non-zero), TP > current_price (if non-zero)
             - SELL: SL > current_price (if non-zero), TP < current_price (if non-zero)
          3. No position currently open

        For CLOSE:
          - Ticket must match an open position

        Returns ValidationResult with valid=True or valid=False with error_reason.
        """
        if cmd.type in (TradeCommandType.BUY, TradeCommandType.SELL):
            # Check lot size
            if not self._validate_lot_size(cmd.lot_size):
                return ValidationResult(
                    valid=False,
                    error_reason=(
                        f"Invalid lot size: {cmd.lot_size:.2f}. "
                        f"Must be between {TRADE_LOT_MIN:.2f} and {TRADE_LOT_MAX:.2f}"
                    ),
                )

            # Check SL/TP levels
            sl_tp_valid, sl_tp_reason = self._validate_stop_levels(
                cmd.stop_loss, cmd.take_profit, cmd.type
            )
            if not sl_tp_valid:
                return ValidationResult(
                    valid=False,
                    error_reason=sl_tp_reason,
                )

            # Check no existing position
            if not self._check_no_existing_position():
                return ValidationResult(
                    valid=False,
                    error_reason=(
                        f"Position already open. Ticket: {self._open_ticket}. "
                        f"Cannot open new {cmd.type.value} position"
                    ),
                )

        elif cmd.type == TradeCommandType.CLOSE:
            if not self._check_ticket_matches_open(cmd.ticket):
                return ValidationResult(
                    valid=False,
                    error_reason=(
                        f"Ticket {cmd.ticket} does not match any open position"
                    ),
                )

        return ValidationResult(valid=True, error_reason="")

    def _validate_lot_size(self, lots: float) -> bool:
        """Check lot size is within [0.01, 100.0]."""
        return TRADE_LOT_MIN <= lots <= TRADE_LOT_MAX

    def _validate_stop_levels(
        self, sl: float, tp: float, cmd_type: TradeCommandType
    ) -> Tuple[bool, str]:
        """
        Validate SL/TP relative to current price.

        Rules:
          - SL >= 0 and TP >= 0 (negative values invalid)
          - 0 means "not set" (valid)
          - BUY: if SL != 0, SL must be < current_price
          - BUY: if TP != 0, TP must be > current_price
          - SELL: if SL != 0, SL must be > current_price
          - SELL: if TP != 0, TP must be < current_price
        """
        # Negative values are always invalid
        if sl < 0:
            return False, f"Invalid SL: {sl:.2f}. Must be >= 0"
        if tp < 0:
            return False, f"Invalid TP: {tp:.2f}. Must be >= 0"

        # Both zero means no SL/TP set - always valid
        if sl == 0.0 and tp == 0.0:
            return True, ""

        price = self._current_price

        if cmd_type == TradeCommandType.BUY:
            # For BUY: SL must be below current price
            if sl != 0.0 and sl >= price:
                return False, (
                    f"Invalid SL for BUY: {sl:.2f} must be below current price {price:.2f}"
                )
            # For BUY: TP must be above current price
            if tp != 0.0 and tp <= price:
                return False, (
                    f"Invalid TP for BUY: {tp:.2f} must be above current price {price:.2f}"
                )

        elif cmd_type == TradeCommandType.SELL:
            # For SELL: SL must be above current price
            if sl != 0.0 and sl <= price:
                return False, (
                    f"Invalid SL for SELL: {sl:.2f} must be above current price {price:.2f}"
                )
            # For SELL: TP must be below current price
            if tp != 0.0 and tp >= price:
                return False, (
                    f"Invalid TP for SELL: {tp:.2f} must be below current price {price:.2f}"
                )

        return True, ""

    def _check_no_existing_position(self) -> bool:
        """Reject BUY/SELL if a position is already open."""
        return not self._has_open_position

    def _check_ticket_matches_open(self, ticket: int) -> bool:
        """Verify CLOSE ticket matches the open position."""
        if not self._has_open_position:
            return False
        return ticket == self._open_ticket
