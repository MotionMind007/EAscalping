"""SQLAlchemy 2.0 async ORM models for the Backend Gateway.

Mirrors the PostgreSQL schema defined in the design document:
- Trade: trade history with full lifecycle tracking
- Candle: OHLCV market data indexed by symbol+timeframe+timestamp
- StateTransition: audit log of all EA state changes
- DailyRisk: daily risk tracking with P/L and lock status
- Signal: signal generation log with indicator values
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    BigInteger,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Trade(Base):
    """Trade history — full lifecycle from PENDING to CLOSED/FAILED."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    lot_size: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    open_price: Mapped[float | None] = mapped_column(Numeric(12, 5), nullable=True)
    close_price: Mapped[float | None] = mapped_column(Numeric(12, 5), nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Numeric(12, 5), nullable=True)
    open_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    signal_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Candle(Base):
    """OHLCV candle data indexed for fast retrieval by symbol+timeframe+timestamp."""

    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_candles_symbol_tf_ts", "symbol", "timeframe", "timestamp", unique=True),
    )


class StateTransition(Base):
    """Audit log for all EA state transition requests and outcomes."""

    __tablename__ = "state_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    from_state: Mapped[str] = mapped_column(String(20), nullable=False)
    to_state: Mapped[str] = mapped_column(String(20), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    command: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DailyRisk(Base):
    """Daily risk tracking record — one row per trading day."""

    __tablename__ = "daily_risk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    starting_equity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    ending_equity: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    daily_pnl: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    max_drawdown_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    risk_lock_activated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    num_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Signal(Base):
    """Signal generation log — records every signal produced by the engine."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    stop_loss: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    take_profit: Mapped[float] = mapped_column(Numeric(12, 5), nullable=False)
    ema_fast: Mapped[float | None] = mapped_column(Numeric(12, 5), nullable=True)
    ema_slow: Mapped[float | None] = mapped_column(Numeric(12, 5), nullable=True)
    rsi: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    spread: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acted_upon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
