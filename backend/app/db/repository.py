"""Repository layer providing async CRUD operations for all database models.

Uses SQLAlchemy 2.0 async sessions. Each method corresponds to a specific
business operation needed by the service layer.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candle, DailyRisk, Signal, StateTransition, Trade


class Repository:
    """Async CRUD repository wrapping a SQLAlchemy AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ─── Trades ───────────────────────────────────────────────────────────

    async def create_trade(self, **kwargs) -> Trade:
        """Create a new trade record (typically in PENDING status)."""
        trade = Trade(**kwargs)
        self.session.add(trade)
        await self.session.flush()
        await self.session.refresh(trade)
        return trade

    async def update_trade_status(self, ticket: Optional[int], **kwargs) -> None:
        """Update trade fields by ticket number.

        If ticket is None (failed trade before ticket assigned), updates the
        most recent PENDING trade.
        """
        if ticket is not None:
            stmt = update(Trade).where(Trade.ticket == ticket).values(**kwargs)
        else:
            # Find latest PENDING trade and update it
            subq = (
                select(Trade.id)
                .where(Trade.status == "PENDING")
                .order_by(Trade.created_at.desc())
                .limit(1)
                .scalar_subquery()
            )
            stmt = update(Trade).where(Trade.id == subq).values(**kwargs)
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_trade_by_ticket(self, ticket: int) -> Optional[Trade]:
        """Retrieve a trade by its MT5 ticket number."""
        result = await self.session.execute(
            select(Trade).where(Trade.ticket == ticket)
        )
        return result.scalar_one_or_none()

    async def get_open_trades(self) -> list[Trade]:
        """Get all trades with status OPEN."""
        result = await self.session.execute(
            select(Trade).where(Trade.status == "OPEN")
        )
        return list(result.scalars().all())

    async def close_trade(
        self,
        ticket: int,
        close_price: float,
        pnl: float,
        close_time: datetime,
    ) -> None:
        """Mark a trade as CLOSED with final metrics."""
        trade = await self.get_trade_by_ticket(ticket)
        if trade is None:
            return

        duration = None
        if trade.open_time:
            duration = int((close_time - trade.open_time).total_seconds())

        stmt = (
            update(Trade)
            .where(Trade.ticket == ticket)
            .values(
                status="CLOSED",
                close_price=close_price,
                realized_pnl=pnl,
                close_time=close_time,
                duration_seconds=duration,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    # ─── Candles ──────────────────────────────────────────────────────────

    async def insert_candle(self, **kwargs) -> Candle:
        """Insert a candle record. Uses ON CONFLICT DO NOTHING for idempotency."""
        candle = Candle(**kwargs)
        self.session.add(candle)
        await self.session.flush()
        await self.session.refresh(candle)
        return candle

    async def get_recent_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Candle]:
        """Get most recent candles for a symbol+timeframe, ordered by timestamp desc."""
        result = await self.session.execute(
            select(Candle)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(Candle.timestamp.desc())
            .limit(limit)
        )
        candles = list(result.scalars().all())
        candles.reverse()  # Return in chronological order
        return candles

    # ─── State Transitions ────────────────────────────────────────────────

    async def log_transition(
        self,
        from_state: str,
        to_state: str,
        approved: bool,
        reason: Optional[str] = None,
        command: Optional[dict] = None,
    ) -> StateTransition:
        """Record a state transition event for audit."""
        transition = StateTransition(
            timestamp=datetime.utcnow(),
            from_state=from_state,
            to_state=to_state,
            approved=approved,
            reason=reason,
            command=command,
        )
        self.session.add(transition)
        await self.session.flush()
        return transition

    # ─── Daily Risk ───────────────────────────────────────────────────────

    async def get_or_create_daily_risk(
        self, target_date: date, starting_equity: float
    ) -> DailyRisk:
        """Get today's risk record or create a new one if it doesn't exist."""
        result = await self.session.execute(
            select(DailyRisk).where(DailyRisk.date == target_date)
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = DailyRisk(date=target_date, starting_equity=starting_equity)
            self.session.add(record)
            await self.session.flush()
            await self.session.refresh(record)
        return record

    async def update_daily_risk(self, target_date: date, **kwargs) -> None:
        """Update daily risk fields for a specific date."""
        stmt = (
            update(DailyRisk)
            .where(DailyRisk.date == target_date)
            .values(**kwargs)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    # ─── Signals ──────────────────────────────────────────────────────────

    async def log_signal(self, **kwargs) -> Signal:
        """Record a generated signal for audit and analysis."""
        signal = Signal(**kwargs)
        self.session.add(signal)
        await self.session.flush()
        await self.session.refresh(signal)
        return signal

    # ─── Orphans ──────────────────────────────────────────────────────────

    async def store_orphan(self, **kwargs) -> Trade:
        """Store an orphan position as a trade record for tracking.

        Orphans are positions found on MT5 that the backend doesn't track.
        They are recorded and scheduled for closure.
        """
        trade = Trade(
            status="OPEN",
            signal_type="ORPHAN",
            **kwargs,
        )
        self.session.add(trade)
        await self.session.flush()
        await self.session.refresh(trade)
        return trade
