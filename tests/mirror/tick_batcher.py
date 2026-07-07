"""
Python mirror implementation of tick batching logic from CMarketCollector
(Include/EAGateway/MarketCollector.mqh).

This module mirrors the batching rules:
  - If tick rate > 10/sec → batch into groups of max 10
  - If tick rate ≤ 10/sec → each tick sent individually (batch of 1)

Feature: ea-gateway
"""

from dataclasses import dataclass
from typing import List


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class Tick:
    """A single tick with a timestamp (seconds from epoch)."""
    timestamp_sec: float
    bid: float = 0.0
    ask: float = 0.0
    spread: int = 0


@dataclass
class TickBatch:
    """A batch of ticks to be sent in a single HTTP POST."""
    ticks: List[Tick]

    @property
    def size(self) -> int:
        return len(self.ticks)


# --------------------------------------------------------------------------
# Tick Batcher (mirrors CMarketCollector batching logic)
# --------------------------------------------------------------------------

class TickBatcher:
    """
    Python mirror of CMarketCollector tick batching logic.

    Batching Rules:
      - Computes the effective tick rate over the given time window
      - If rate > 10 ticks/sec: batch ticks into groups of at most 10
      - If rate ≤ 10 ticks/sec: each tick is sent individually (batch of 1)
    """

    MAX_BATCH_SIZE = 10
    RATE_THRESHOLD = 10  # ticks per second

    def batch_ticks(self, ticks: List[Tick]) -> List[TickBatch]:
        """
        Batch a sequence of ticks based on effective tick rate.

        Given N ticks over time window T:
        - If N/T > 10 ticks/sec → batch into groups of max 10
        - If N/T ≤ 10 ticks/sec → each tick sent individually

        For sequences with 0 or 1 ticks, or zero time window,
        each tick is sent individually.

        Args:
            ticks: List of ticks in chronological order

        Returns:
            List of TickBatch objects
        """
        if not ticks:
            return []

        if len(ticks) == 1:
            return [TickBatch(ticks=[ticks[0]])]

        # Calculate effective tick rate
        time_window = ticks[-1].timestamp_sec - ticks[0].timestamp_sec

        if time_window <= 0:
            # All ticks have the same timestamp (or out of order)
            # Treat as high rate → batch
            return self._batch_into_groups(ticks)

        rate = len(ticks) / time_window

        if rate > self.RATE_THRESHOLD:
            # High rate: batch into groups of max 10
            return self._batch_into_groups(ticks)
        else:
            # Low rate: send each tick individually
            return [TickBatch(ticks=[t]) for t in ticks]

    def _batch_into_groups(self, ticks: List[Tick]) -> List[TickBatch]:
        """Split ticks into groups of at most MAX_BATCH_SIZE."""
        batches = []
        for i in range(0, len(ticks), self.MAX_BATCH_SIZE):
            chunk = ticks[i:i + self.MAX_BATCH_SIZE]
            batches.append(TickBatch(ticks=chunk))
        return batches
