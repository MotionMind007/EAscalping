"""Position Manager — Track open/closed positions.

Manages the currently open position (at most 1) in Redis.
Handles orphan detection and issues CLOSE commands for orphan positions.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""
import json
from typing import Optional

from redis.asyncio import Redis

from app.models.enums import CommandType
from app.models.requests import OrphanPayload, PositionStatusPayload
from app.models.responses import TradeCommand


class PositionManager:
    """Tracks the currently open position (max 1) in Redis.

    Responsible for:
    - Storing/retrieving open position details
    - Updating position with current price/P&L
    - Marking positions as closed
    - Handling orphan positions (issuing CLOSE commands)
    """

    KEY_POSITION = "position:open"

    def __init__(self, redis: Redis):
        self._redis = redis

    async def get_known_tickets(self) -> list[int]:
        """Return list of ticket numbers currently tracked as open.

        At most 1 ticket for this system (one position at a time rule).

        Returns:
            List containing the open ticket number, or empty list.
        """
        raw = await self._redis.get(self.KEY_POSITION)
        if raw is None:
            return []
        data = json.loads(raw)
        ticket = data.get("ticket")
        return [ticket] if ticket is not None else []

    async def has_open_position(self) -> bool:
        """Check if a position is currently tracked.

        Returns:
            True if a position record exists in Redis.
        """
        return await self._redis.get(self.KEY_POSITION) is not None

    async def record_open_position(
        self, ticket: int, direction: str, lot_size: float, open_price: float
    ) -> None:
        """Store open position details in Redis.

        Args:
            ticket: MT5 ticket number.
            direction: Trade direction ("BUY" or "SELL").
            lot_size: Position lot size.
            open_price: Position open price.
        """
        data = json.dumps({
            "ticket": ticket,
            "direction": direction,
            "lot_size": lot_size,
            "open_price": open_price,
        })
        await self._redis.set(self.KEY_POSITION, data)

    async def update_position_status(self, payload: PositionStatusPayload) -> None:
        """Update position with current price and unrealized P/L.

        Args:
            payload: Position status data from the EA.
        """
        data = json.dumps({
            "ticket": payload.ticket,
            "symbol": payload.symbol,
            "direction": payload.direction.value,
            "lot_size": payload.lot_size,
            "open_price": payload.open_price,
            "current_price": payload.current_price,
            "unrealized_pnl": payload.unrealized_pnl,
            "timestamp": payload.timestamp,
        })
        await self._redis.set(self.KEY_POSITION, data)

    async def mark_position_closed(self) -> None:
        """Remove open position from Redis (position closed)."""
        await self._redis.delete(self.KEY_POSITION)

    async def handle_orphan(self, orphan: OrphanPayload) -> TradeCommand:
        """Handle orphan position: return CLOSE command.

        Orphan positions are positions that exist in MT5 but are not
        tracked by the backend. The only valid action is to close them.

        Args:
            orphan: Orphan position details from the EA.

        Returns:
            TradeCommand with type=CLOSE for the orphan position.
        """
        return TradeCommand(
            type=CommandType.CLOSE,
            lot_size=orphan.lot_size,
            stop_loss=0.01,  # Placeholder (not used for CLOSE)
            take_profit=0.01,  # Placeholder (not used for CLOSE)
            ticket=orphan.ticket,
        )
