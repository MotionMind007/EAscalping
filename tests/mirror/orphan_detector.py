"""
Python mirror implementation of orphan position detection logic
(Include/EAGateway/HealthMonitor.mqh - CheckOrphanPositions).

This module mirrors the set comparison logic for identifying orphan positions:
positions that exist in MT5 but are NOT known to the backend.

Feature: ea-gateway
"""

from dataclasses import dataclass
from typing import Set, List, FrozenSet


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Position:
    """Represents an open position identified by ticket number."""
    ticket: int
    symbol: str = "XAUUSD"
    direction: str = "BUY"
    lot_size: float = 0.1
    open_price: float = 2035.0


# --------------------------------------------------------------------------
# Orphan Detector (mirror of CHealthMonitor::CheckOrphanPositions)
# --------------------------------------------------------------------------

class OrphanDetector:
    """
    Python mirror of the orphan position detection logic.

    An orphan position is one that exists in the MT5 open positions set
    but is NOT known to the backend. The detection compares the two sets
    and reports all positions in (MT5 - Backend).

    Mirrors CHealthMonitor::CheckOrphanPositions() from HealthMonitor.mqh:
    1. Query backend for known open positions (set of ticket numbers)
    2. Get MT5 open positions (set of ticket numbers)
    3. Orphans = MT5 positions NOT in backend set
    4. Report all orphans to backend
    """

    def detect_orphans(
        self,
        mt5_positions: Set[int],
        backend_known_positions: Set[int],
    ) -> Set[int]:
        """
        Detect orphan positions by set difference.

        Orphans = MT5 positions that are NOT known to the backend.

        Args:
            mt5_positions: Set of ticket numbers currently open in MT5
            backend_known_positions: Set of ticket numbers the backend knows about

        Returns:
            Set of orphan ticket numbers (MT5 - backend)
        """
        return mt5_positions - backend_known_positions

    def detect_orphans_with_details(
        self,
        mt5_positions: List[Position],
        backend_known_tickets: Set[int],
    ) -> List[Position]:
        """
        Detect orphan positions and return full position details.

        Args:
            mt5_positions: List of Position objects currently open in MT5
            backend_known_tickets: Set of ticket numbers the backend knows about

        Returns:
            List of Position objects that are orphans (not in backend)
        """
        return [
            pos for pos in mt5_positions
            if pos.ticket not in backend_known_tickets
        ]

    def all_orphans_reported(
        self,
        mt5_positions: Set[int],
        backend_known_positions: Set[int],
        reported_orphans: Set[int],
    ) -> bool:
        """
        Verify that all orphan positions have been reported.

        Args:
            mt5_positions: Set of ticket numbers currently open in MT5
            backend_known_positions: Set of ticket numbers the backend knows about
            reported_orphans: Set of ticket numbers that were reported as orphans

        Returns:
            True if reported_orphans == (mt5_positions - backend_known_positions)
        """
        expected_orphans = mt5_positions - backend_known_positions
        return reported_orphans == expected_orphans
