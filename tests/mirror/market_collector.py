"""
Python mirror implementation of CMarketCollector state guard logic
(Include/EAGateway/MarketCollector.mqh).

This module mirrors the state guard that determines whether market data
(ticks and candles) should be collected and forwarded based on the current
EA state. Data is only collected/forwarded when the EA is past the CONNECT
state (i.e., not in BOOT or CONNECT).

Feature: ea-gateway
"""

from enum import Enum
from dataclasses import dataclass
from typing import List


# --------------------------------------------------------------------------
# EAState enum (reuse from state_machine mirror)
# --------------------------------------------------------------------------

class EAState(Enum):
    BOOT = "BOOT"
    CONNECT = "CONNECT"
    WAIT_SESSION = "WAIT_SESSION"
    CHECK_RISK = "CHECK_RISK"
    SCAN_SIGNAL = "SCAN_SIGNAL"
    AI_CONFIRMATION = "AI_CONFIRMATION"
    OPEN_POSITION = "OPEN_POSITION"
    MANAGE_POSITION = "MANAGE_POSITION"
    POSITION_CLOSED = "POSITION_CLOSED"
    DISCONNECTED = "DISCONNECTED"


# --------------------------------------------------------------------------
# States classification
# --------------------------------------------------------------------------

# States where market data collection is BLOCKED
BLOCKED_STATES = frozenset([EAState.BOOT, EAState.CONNECT])

# States where market data collection is ALLOWED
ALLOWED_STATES = frozenset([
    EAState.WAIT_SESSION,
    EAState.CHECK_RISK,
    EAState.SCAN_SIGNAL,
    EAState.AI_CONFIRMATION,
    EAState.OPEN_POSITION,
    EAState.MANAGE_POSITION,
    EAState.POSITION_CLOSED,
    EAState.DISCONNECTED,
])

ALL_STATES = list(EAState)


# --------------------------------------------------------------------------
# Market data structures
# --------------------------------------------------------------------------

@dataclass
class TickData:
    timestamp: str = ""
    bid: float = 0.0
    ask: float = 0.0
    spread: int = 0


@dataclass
class CandleData:
    timestamp: str = ""
    timeframe: str = "M1"
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0


# --------------------------------------------------------------------------
# MarketCollector state guard (mirrors CMarketCollector guard logic)
# --------------------------------------------------------------------------

class MarketCollector:
    """
    Python mirror of CMarketCollector state guard logic.

    The collector only collects and forwards market data when the EA
    is in an allowed state (any state after CONNECT).
    """

    def __init__(self):
        self._collected_ticks: List[TickData] = []
        self._collected_candles: List[CandleData] = []

    def should_collect(self, current_state: EAState) -> bool:
        """
        Determine if market data should be collected in the given state.

        Returns True if the state is after CONNECT (not BOOT or CONNECT).
        Mirrors the guard check in CMarketCollector::OnTick() and OnNewBar().
        """
        return current_state not in BLOCKED_STATES

    def on_tick(self, current_state: EAState, tick: TickData) -> bool:
        """
        Process an incoming tick event.

        Returns True if the tick was collected (state allows it),
        False if the tick was dropped (state blocks it).
        """
        if not self.should_collect(current_state):
            return False

        self._collected_ticks.append(tick)
        return True

    def on_new_bar(self, current_state: EAState, candle: CandleData) -> bool:
        """
        Process a new bar (candle close) event.

        Returns True if the candle was collected (state allows it),
        False if the candle was dropped (state blocks it).
        """
        if not self.should_collect(current_state):
            return False

        self._collected_candles.append(candle)
        return True

    @property
    def collected_ticks(self) -> List[TickData]:
        """Return all collected ticks."""
        return self._collected_ticks

    @property
    def collected_candles(self) -> List[CandleData]:
        """Return all collected candles."""
        return self._collected_candles

    def clear(self):
        """Reset collected data."""
        self._collected_ticks.clear()
        self._collected_candles.clear()
