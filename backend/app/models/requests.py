"""Pydantic request schemas for the Backend Gateway API.

All incoming payloads from the EA are validated against these models.
Invalid payloads automatically return HTTP 422 with detailed error messages.
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .enums import CommandType, Direction, EAState


# ─── Market endpoints ────────────────────────────────────────────────────────


class TickItem(BaseModel):
    """A single tick data point within a tick payload."""

    timestamp: str = Field(..., description="ISO timestamp of the tick")
    bid: float = Field(..., gt=0, description="Bid price")
    ask: float = Field(..., gt=0, description="Ask price")
    spread: int = Field(..., ge=0, description="Spread in points")


class TickPayload(BaseModel):
    """POST /api/v1/market/tick — tick data from the EA."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol")
    ticks: list[TickItem] = Field(..., min_length=1, description="Array of tick data")


class CandlePayload(BaseModel):
    """POST /api/v1/market/candle — candle data from the EA."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol")
    timeframe: str = Field(..., min_length=1, max_length=5, description="Timeframe (M1, M5, etc.)")
    timestamp: str = Field(..., description="Candle open time (ISO format)")
    open: float = Field(..., gt=0, description="Open price")
    high: float = Field(..., gt=0, description="High price")
    low: float = Field(..., gt=0, description="Low price")
    close: float = Field(..., gt=0, description="Close price")
    volume: int = Field(..., ge=0, description="Tick volume")

    @field_validator("high")
    @classmethod
    def high_must_be_highest(cls, v: float, info) -> float:
        """High must be >= open and low."""
        data = info.data
        for field_name in ("open", "low"):
            other = data.get(field_name)
            if other is not None and v < other:
                raise ValueError(f"high ({v}) must be >= {field_name} ({other})")
        return v

    @field_validator("low")
    @classmethod
    def low_must_be_lowest(cls, v: float, info) -> float:
        """Low must be <= open and high."""
        data = info.data
        for field_name in ("open", "high"):
            other = data.get(field_name)
            if other is not None and v > other:
                raise ValueError(f"low ({v}) must be <= {field_name} ({other})")
        return v


# ─── Health endpoints ────────────────────────────────────────────────────────


class HeartbeatPayload(BaseModel):
    """POST /api/v1/health/heartbeat — EA health status report."""

    state: EAState = Field(..., description="Current EA state")
    account_balance: float = Field(..., ge=0, description="Account balance")
    account_equity: float = Field(..., ge=0, description="Account equity")
    latency_ms: int = Field(..., ge=0, description="Round-trip latency in ms")
    mt5_connected: bool = Field(..., description="Whether EA is connected to MT5")
    spread: int = Field(..., ge=0, description="Current spread in points")
    timestamp: str = Field(..., description="ISO timestamp of the heartbeat")


class MT5DisconnectPayload(BaseModel):
    """POST /api/v1/health/mt5disconnect — MT5 connection lost."""

    event: str = Field(..., min_length=1, description="Event type identifier")
    state: EAState = Field(..., description="EA state at time of disconnect")
    timestamp: str = Field(..., description="ISO timestamp of disconnect event")


class MT5ReconnectPayload(BaseModel):
    """POST /api/v1/health/mt5reconnect — MT5 connection restored."""

    event: str = Field(..., min_length=1, description="Event type identifier")
    state: EAState = Field(..., description="EA state at time of reconnect")
    account_balance: float = Field(..., ge=0, description="Account balance after reconnect")
    account_equity: float = Field(..., ge=0, description="Account equity after reconnect")
    timestamp: str = Field(..., description="ISO timestamp of reconnect event")


# ─── State endpoints ─────────────────────────────────────────────────────────


class TransitionRequest(BaseModel):
    """POST /api/v1/state/transition — EA requesting state change."""

    current_state: EAState = Field(..., description="Current EA state")
    requested_state: EAState = Field(..., description="Requested target state")
    reason: str = Field(..., min_length=1, description="Reason for the transition request")
    timestamp: str = Field(..., description="ISO timestamp of the request")


class RecoveryPayload(BaseModel):
    """POST /api/v1/state/recovery — EA recovery after disconnect/restart."""

    current_state: EAState = Field(..., description="EA's current state on recovery")
    open_position: Optional[dict] = Field(
        default=None, description="Open position details if any"
    )
    account_equity: float = Field(..., ge=0, description="Current account equity")
    timestamp: str = Field(..., description="ISO timestamp of recovery report")


# ─── Trade endpoints ─────────────────────────────────────────────────────────


class TradeResultPayload(BaseModel):
    """POST /api/v1/trade/result — trade execution result from EA."""

    success: bool = Field(..., description="Whether the trade command executed successfully")
    ticket: Optional[int] = Field(
        default=None, ge=0, description="MT5 ticket number (present on success)"
    )
    error_code: Optional[int] = Field(
        default=None, description="MT5 error code (present on failure)"
    )
    fill_price: Optional[float] = Field(
        default=None, gt=0, description="Actual fill price (present on success)"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error description (present on failure)"
    )
    command_type: CommandType = Field(..., description="Type of command that was executed")
    slippage_points: Optional[int] = Field(
        default=None, ge=0, description="Actual slippage in points"
    )
    timestamp: str = Field(..., description="ISO timestamp of the trade result")


# ─── Position endpoints ──────────────────────────────────────────────────────


class PositionStatusPayload(BaseModel):
    """POST /api/v1/position/status — current position status from EA."""

    ticket: int = Field(..., ge=0, description="MT5 ticket number")
    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol")
    direction: Direction = Field(..., description="Trade direction (BUY or SELL)")
    lot_size: float = Field(..., gt=0, le=10.0, description="Position lot size")
    open_price: float = Field(..., gt=0, description="Position open price")
    current_price: float = Field(..., gt=0, description="Current market price")
    unrealized_pnl: float = Field(..., description="Unrealized profit/loss")
    timestamp: str = Field(..., description="ISO timestamp of the status report")


class OrphanPayload(BaseModel):
    """POST /api/v1/position/orphan — orphan position detected by EA."""

    ticket: int = Field(..., ge=0, description="MT5 ticket number of orphan position")
    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol")
    direction: Direction = Field(..., description="Trade direction")
    lot_size: float = Field(..., gt=0, le=10.0, description="Position lot size")
    open_price: float = Field(..., gt=0, description="Position open price")
    open_time: str = Field(..., description="ISO timestamp when position was opened")


class PositionKnownRequest(BaseModel):
    """POST /api/v1/position/known — query known positions for a symbol."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol to query")
