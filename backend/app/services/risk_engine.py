"""Risk Engine — Daily P/L tracking and RISK_LOCK enforcement.

Tracks accumulated daily profit/loss and activates RISK_LOCK when
the loss exceeds the configured max_daily_loss_pct threshold.

Redis keys used:
- risk:daily_pnl     — float string, accumulated P/L for today
- risk:lock          — "1" if RISK_LOCK active
- risk:starting_equity — float string, today's starting equity
"""
from redis.asyncio import Redis

from app.config import Settings


class RiskEngine:
    """Daily P/L tracking and RISK_LOCK management.

    Args:
        redis: Async Redis client for fast state access.
        settings: Application settings with max_daily_loss_pct.
    """

    # Redis key constants
    KEY_DAILY_PNL = "risk:daily_pnl"
    KEY_LOCK = "risk:lock"
    KEY_STARTING_EQUITY = "risk:starting_equity"

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def get_status(self) -> str:
        """Return 'RISK_LOCK' if lock flag is set, else 'CLEAR'."""
        lock_value = await self._redis.get(self.KEY_LOCK)
        if lock_value is not None and lock_value == "1":
            return "RISK_LOCK"
        return "CLEAR"

    async def record_trade_pnl(self, pnl: float) -> None:
        """Accumulate trade P/L and activate lock if threshold breached.

        Args:
            pnl: The realized profit/loss of the closed trade.
        """
        daily_pnl = await self.get_daily_pnl()
        daily_pnl += pnl
        await self._redis.set(self.KEY_DAILY_PNL, str(daily_pnl))

        starting_equity = await self.get_starting_equity()
        if starting_equity > 0:
            loss_pct = self.calculate_loss_pct(daily_pnl, starting_equity)
            if loss_pct >= self._settings.max_daily_loss_pct:
                await self._redis.set(self.KEY_LOCK, "1")

    async def reset_daily(self, new_equity: float) -> None:
        """Reset at 00:00 UTC — clear lock, zero out P/L, record new equity.

        Args:
            new_equity: The account equity at the start of the new day.
        """
        await self._redis.delete(self.KEY_LOCK)
        await self._redis.set(self.KEY_DAILY_PNL, "0.0")
        await self._redis.set(self.KEY_STARTING_EQUITY, str(new_equity))

    def calculate_loss_pct(self, daily_pnl: float, starting_equity: float) -> float:
        """Pure function: compute loss percentage.

        Formula: abs(min(daily_pnl, 0)) / starting_equity * 100

        Returns 0.0 if daily_pnl >= 0 (no loss).
        """
        if starting_equity <= 0:
            return 0.0
        return abs(min(daily_pnl, 0)) / starting_equity * 100

    async def get_daily_pnl(self) -> float:
        """Read current accumulated daily P/L from Redis."""
        value = await self._redis.get(self.KEY_DAILY_PNL)
        if value is None:
            return 0.0
        return float(value)

    async def get_starting_equity(self) -> float:
        """Read today's starting equity from Redis."""
        value = await self._redis.get(self.KEY_STARTING_EQUITY)
        if value is None:
            return 0.0
        return float(value)

    async def initialize(self, current_equity: float) -> None:
        """Called on startup to set initial equity if not already set.

        Only sets starting equity if no value exists in Redis (avoids
        overwriting mid-day on restart).

        Args:
            current_equity: Current account equity at startup time.
        """
        existing = await self._redis.get(self.KEY_STARTING_EQUITY)
        if existing is None:
            await self._redis.set(self.KEY_STARTING_EQUITY, str(current_equity))
            await self._redis.set(self.KEY_DAILY_PNL, "0.0")
