"""Trade router — trade execution result reporting.

Receives trade execution results from the EA (success/failure of commands).
Wires to TradeOrchestrator for trade record updates and PositionManager for open position tracking.
"""
import logging

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_settings, get_redis, verify_auth_token
from app.models.requests import TradeResultPayload
from app.models.responses import TradeCommand
from app.services.position_manager import PositionManager
from app.services.trade_orchestrator import TradeOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trade", tags=["trade"])


async def get_trade_orchestrator(redis, settings: Settings = Depends(get_settings)) -> TradeOrchestrator:
    """Provide TradeOrchestrator instance with dependencies."""
    return TradeOrchestrator(redis=redis, settings=settings)


async def get_position_manager(redis) -> PositionManager:
    """Provide PositionManager instance with dependencies."""
    return PositionManager(redis=redis)


@router.post("/result", dependencies=[Depends(verify_auth_token)])
async def receive_trade_result(
    payload: TradeResultPayload,
    orchestrator: TradeOrchestrator = Depends(get_trade_orchestrator),
    position_manager: PositionManager = Depends(get_position_manager),
) -> dict:
    """Process trade result from the EA.

    - On success: updates trade record to OPEN, records position in PositionManager
    - On failure: updates trade record to FAILED with error details

    Requirements: 5.5, 5.6, 6.1
    """
    # Record trade result in TradeOrchestrator (updates Redis trade records)
    await orchestrator.record_trade_result(
        success=payload.success,
        ticket=payload.ticket if payload.success else None,
        fill_price=payload.fill_price if payload.success else None,
        error_code=payload.error_code if not payload.success else None,
        error_message=payload.error_message if not payload.success else None,
    )

    if payload.success:
        # On successful trade, record the open position in PositionManager
        # Direction is derived from the command_type in the payload
        direction = payload.command_type.upper() if payload.command_type else None
        if direction and direction in ("BUY", "SELL"):
            await position_manager.record_open_position(
                ticket=payload.ticket,
                direction=direction,
                lot_size=orchestrator._settings.lot_size,
                open_price=payload.fill_price,
            )
        logger.info(
            "Trade result: SUCCESS ticket=%s fill_price=%s command=%s",
            payload.ticket,
            payload.fill_price,
            payload.command_type,
        )
    else:
        logger.warning(
            "Trade result: FAILED error_code=%s error_message=%s command=%s",
            payload.error_code,
            payload.error_message,
            payload.command_type,
        )

    return {}
