"""Initial schema - trades, candles, state_transitions, daily_risk, signals

Revision ID: 001
Revises: None
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- trades table ---
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket", sa.BigInteger(), unique=True, nullable=True),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("lot_size", sa.Numeric(10, 2), nullable=False),
        sa.Column("open_price", sa.Numeric(12, 5), nullable=True),
        sa.Column("close_price", sa.Numeric(12, 5), nullable=True),
        sa.Column("fill_price", sa.Numeric(12, 5), nullable=True),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(12, 2), nullable=True),
        sa.Column("signal_type", sa.String(20), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- candles table ---
    op.create_table(
        "candles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(12, 5), nullable=False),
        sa.Column("high", sa.Numeric(12, 5), nullable=False),
        sa.Column("low", sa.Numeric(12, 5), nullable=False),
        sa.Column("close", sa.Numeric(12, 5), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_candle"),
    )

    # --- state_transitions table ---
    op.create_table(
        "state_transitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_state", sa.String(20), nullable=False),
        sa.Column("to_state", sa.String(20), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("command", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- daily_risk table ---
    op.create_table(
        "daily_risk",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), unique=True, nullable=False),
        sa.Column("starting_equity", sa.Numeric(12, 2), nullable=False),
        sa.Column("ending_equity", sa.Numeric(12, 2), nullable=True),
        sa.Column("daily_pnl", sa.Numeric(12, 2), server_default="0"),
        sa.Column("max_drawdown_pct", sa.Numeric(5, 2), server_default="0"),
        sa.Column("risk_lock_activated", sa.Boolean(), server_default="false"),
        sa.Column("num_trades", sa.Integer(), server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- signals table ---
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("entry_price", sa.Numeric(12, 5), nullable=False),
        sa.Column("stop_loss", sa.Numeric(12, 5), nullable=False),
        sa.Column("take_profit", sa.Numeric(12, 5), nullable=False),
        sa.Column("ema_fast", sa.Numeric(12, 5), nullable=True),
        sa.Column("ema_slow", sa.Numeric(12, 5), nullable=True),
        sa.Column("rsi", sa.Numeric(5, 2), nullable=True),
        sa.Column("spread", sa.Integer(), nullable=True),
        sa.Column("acted_upon", sa.Boolean(), server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("signals")
    op.drop_table("daily_risk")
    op.drop_table("state_transitions")
    op.drop_table("candles")
    op.drop_table("trades")
