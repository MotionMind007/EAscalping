"""Pydantic response schemas for the Backend Gateway API.

All outgoing responses are serialized through these models to ensure
consistent JSON structure for the EA client.
"""
from typing import Optional

from pydantic import BaseModel, Field

from .enums import CommandType, EAState


# ─── Trade Command ───────────────────────────────────────────────────────────


class TradeCommand(BaseModel):
    """A command sent to the EA to execute a trade action."""

    type: CommandType = Field(..., description="Command type: BUY, SELL, or CLOSE")
    lot_size: float = Field(..., gt=0, le=10.0, description="Lot size to trade")
    stop_loss: float = Field(..., gt=0, description="Stop loss price level")
    take_profit: float = Field(..., gt=0, description="Take profit price level")
    ticket: Optional[int] = Field(
        default=None, ge=0, description="Ticket number (required for CLOSE commands)"
    )


# ─── State endpoints ─────────────────────────────────────────────────────────


class TransitionResponse(BaseModel):
    """Response to POST /api/v1/state/transition."""

    approved: bool = Field(..., description="Whether the transition was approved")
    new_state: EAState = Field(..., description="The resulting state after the decision")
    command: Optional[TradeCommand] = Field(
        default=None, description="Trade command to execute (if any)"
    )
    reason: Optional[str] = Field(
        default=None, description="Reason for rejection (if not approved)"
    )


class RecoveryResponse(BaseModel):
    """Response to POST /api/v1/state/recovery."""

    confirmed_state: EAState = Field(..., description="Confirmed EA state after reconciliation")
    pending_commands: list[TradeCommand] = Field(
        default_factory=list, description="Any pending commands to execute"
    )


# ─── Health endpoints ────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response to GET /health — system-level health status."""

    status: str = Field(..., description="System health: healthy, degraded, or unhealthy")
    ea_connected: bool = Field(
        ..., description="Whether EA heartbeat is recent (< 90 seconds)"
    )
    last_heartbeat_age_seconds: float = Field(
        ..., ge=0, description="Seconds since last heartbeat"
    )
    redis_connected: bool = Field(..., description="Whether Redis is reachable")
    postgres_connected: bool = Field(..., description="Whether PostgreSQL is reachable")
    risk_lock_active: bool = Field(..., description="Whether RISK_LOCK is currently active")
    current_state: Optional[EAState] = Field(
        default=None, description="Current EA state (None if unknown/disconnected)"
    )


# ─── Position endpoints ──────────────────────────────────────────────────────


class PositionKnownResponse(BaseModel):
    """Response to POST /api/v1/position/known."""

    tickets: list[int] = Field(
        default_factory=list, description="List of currently tracked open ticket numbers"
    )


# ─── Error ───────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str = Field(..., description="Human-readable error description")
