"""Position router — position tracking and orphan detection.

Handles position status updates, known position queries, and orphan
position resolution. Stores position state in Redis for fast access.
"""
import json
import logging

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.dependencies import get_redis, verify_auth_token
from app.models.enums import CommandType
from app.models.requests import OrphanPayload, PositionKnownRequest, PositionStatusPayload
from app.models.responses import PositionKnownResponse, TradeCommand
from app.services import PositionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/position", tags=["position"])


# ─── Dependencies ─────────────────────────────────────────────────────────────


async def get_position_manager(redis: Redis = Depends(get_redis)) -> PositionManager:
    """Provide PositionManager instance to route handlers."""
    return PositionManager(redis)


@router.post("/status", dependencies=[Depends(verify_auth_token)])
async def receive_position_status(
    payload: PositionStatusPayload,
    position_manager: PositionManager = Depends(get_position_manager),
) -> dict:
    """Store current position status in Redis via PositionManager.

    Delegates to PositionManager.update_position_status() to handle
    storing position details in Redis.
    """
    await position_manager.update_position_status(payload)
    logger.info(
        "Position status stored: ticket=%d symbol=%s direction=%s pnl=%.2f",
        payload.ticket,
        payload.symbol,
        payload.direction.value,
        payload.unrealized_pnl,
    )
    return {}


@router.post("/known", dependencies=[Depends(verify_auth_token)])
async def get_known_positions(
    payload: PositionKnownRequest,
    position_manager: PositionManager = Depends(get_position_manager),
) -> PositionKnownResponse:
    """Return list of ticket numbers currently tracked as open via PositionManager.

    Delegates to PositionManager.get_known_tickets() to retrieve
    the list of open tickets from Redis.
    """
    tickets = await position_manager.get_known_tickets()
    return PositionKnownResponse(tickets=tickets)


@router.post("/orphan", dependencies=[Depends(verify_auth_token)])
async def handle_orphan_position(
    payload: OrphanPayload,
    position_manager: PositionManager = Depends(get_position_manager),
) -> TradeCommand:
    """Handle an orphan position via PositionManager.

    Delegates to PositionManager.handle_orphan() to return a CLOSE
    command for the orphan position.
    """
    logger.warning(
        "Orphan position detected: ticket=%d symbol=%s direction=%s lot_size=%.2f open_price=%.5f",
        payload.ticket,
        payload.symbol,
        payload.direction.value,
        payload.lot_size,
        payload.open_price,
    )
    return await position_manager.handle_orphan(payload)
