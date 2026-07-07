"""
Python mirror implementation of CSessionManager (Include/EAGateway/SessionManager.mqh).

This module provides the same logic as the MQL5 implementation for property-based testing.
It mirrors:
  - Session time identification (LONDON, OVERLAP, NEW_YORK, OFF)
  - Combined session window check (IsInSession)
  - Individual session checks (IsLondonSession, IsNewYorkSession)
  - Trade permission logic (CanOpenTrade, CanCloseTrade)

Feature: ea-gateway
"""

from enum import Enum
from typing import Tuple


# --------------------------------------------------------------------------
# Session Name Enum
# --------------------------------------------------------------------------

class SessionName(Enum):
    LONDON = "LONDON"
    OVERLAP = "OVERLAP"
    NEW_YORK = "NEW_YORK"
    OFF = "OFF"


# --------------------------------------------------------------------------
# Trade Command Types (for command filtering tests)
# --------------------------------------------------------------------------

class TradeCommandType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"


# --------------------------------------------------------------------------
# CSessionManager Mirror
# --------------------------------------------------------------------------

class SessionManager:
    """
    Python mirror of CSessionManager from SessionManager.mqh.

    Session definitions (all UTC):
      London:   08:00 - 16:00 (inclusive start, exclusive end)
      New York: 13:00 - 21:00 (inclusive start, exclusive end)
      Overlap:  13:00 - 16:00 (both London and NY active)
      Combined: 08:00 - 21:00 (any active session)

    Session name logic:
      LONDON:   8 <= H < 13  (London-only, before NY overlap)
      OVERLAP: 13 <= H < 16  (both London and NY active)
      NEW_YORK: 16 <= H < 21  (NY-only, after London closes)
      OFF:      H < 8 or H >= 21
    """

    def __init__(self):
        self.london_start_hour = 8
        self.london_end_hour = 16
        self.ny_start_hour = 13
        self.ny_end_hour = 21

    def is_in_session(self, hour: int) -> bool:
        """
        Combined session window: true if UTC hour is in [8, 21).
        London OR New York active.
        """
        return self.london_start_hour <= hour < self.ny_end_hour

    def is_london_session(self, hour: int) -> bool:
        """London session: true if UTC hour is in [8, 16)."""
        return self.london_start_hour <= hour < self.london_end_hour

    def is_new_york_session(self, hour: int) -> bool:
        """New York session: true if UTC hour is in [13, 21)."""
        return self.ny_start_hour <= hour < self.ny_end_hour

    def get_current_session_name(self, hour: int) -> SessionName:
        """
        Returns the session name for a given UTC hour.

        Logic (matches MQL5 implementation):
          OFF:       H < 8 or H >= 21
          OVERLAP:  13 <= H < 16 (both London and NY active)
          LONDON:    8 <= H < 13 (London-only, before NY starts)
          NEW_YORK: 16 <= H < 21 (NY-only, after London closes)
        """
        # Check OFF first (outside any session)
        if hour < self.london_start_hour or hour >= self.ny_end_hour:
            return SessionName.OFF

        # Overlap: both London and NY are active [13, 16)
        if hour >= self.ny_start_hour and hour < self.london_end_hour:
            return SessionName.OVERLAP

        # London-only: [8, 13) - before NY starts
        if hour >= self.london_start_hour and hour < self.ny_start_hour:
            return SessionName.LONDON

        # New York-only: [16, 21) - after London closes
        if hour >= self.london_end_hour and hour < self.ny_end_hour:
            return SessionName.NEW_YORK

        # Defensive (should not reach here)
        return SessionName.OFF

    def can_open_trade(self, hour: int) -> bool:
        """BUY/SELL allowed only if in session (combined window)."""
        return self.is_in_session(hour)

    def can_close_trade(self) -> bool:
        """CLOSE always allowed regardless of session time."""
        return True

    def filter_command(self, command_type: TradeCommandType, hour: int) -> Tuple[bool, str]:
        """
        Session-based command filtering.

        Returns:
            (accepted, reason) tuple.
            - BUY/SELL: rejected if outside session window
            - CLOSE: always accepted
        """
        if command_type in (TradeCommandType.BUY, TradeCommandType.SELL):
            if not self.is_in_session(hour):
                return False, "Trade rejected: outside session window"
            return True, ""
        elif command_type == TradeCommandType.CLOSE:
            return True, ""
        else:
            return False, f"Unknown command type: {command_type}"
