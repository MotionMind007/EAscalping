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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/position", tags=["position"])


@router.post("/status", dependencies=[Depends(verify_auth_token)])
async def receive_position_status(
    payload: PositionStatusPayload,
    redis: Redis = Depends(get_redis),
) -> dict:
    """Store current position status in Redis.

    Stores position details as JSON at key `position:open` for fast
    retrieval by the /position/known endpoint and other services.
    """
    position_data = json.dumps({
        "ticket": payload.ticket,
        "symbol": payload.symbol,
        "direction": payload.direction.value,
        "lot_size": payload.lot_size,
        "open_price": payload.open_price,
        "current_price": payload.current_price,
        "unrealized_pnl": payload.unrealized_pnl,
        "timestamp": payload.timestamp,
    })
    await redis.set("position:open", position_data)
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
    redis: Redis = Depends(get_redis),
) -> PositionKnownResponse:
    """Return list of ticket numbers currently tracked as open.

    Reads the `position:open` Redis key. If a position exists, returns
    its ticket in the tickets list. Otherwise returns an empty list.
    """
    raw = await redis.get("position:open")
    if raw is None:
        return PositionKnownResponse(tickets=[])

    position = json.loads(raw)
    ticket = position.get("ticket")
    if ticket is not None:
        return PositionKnownResponse(tickets=[ticket])

    return PositionKnownResponse(tickets=[])


@router.post("/orphan", dependencies=[Depends(verify_auth_token)])
async def handle_orphan_position(payload: OrphanPayload) -> TradeCommand:
    """Handle an orphan position detected by the EA.

    Logs the orphan and returns a CLOSE command with the orphan's ticket
    so the EA closes the untracked position.
    """
    logger.warning(
        "Orphan position detected: ticket=%d symbol=%s direction=%s lot_size=%.2f open_price=%.5f",
        payload.ticket,
        payload.symbol,
        payload.direction.value,
        payload.lot_size,
        payload.open_price,
    )
    return TradeCommand(
        type=CommandType.CLOSE,
        lot_size=payload.lot_size,
        stop_loss=0.01,
        take_profit=0.01,
        ticket=payload.ticket,
    )
