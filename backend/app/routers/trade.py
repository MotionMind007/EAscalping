"""Trade router — trade execution result reporting.

Receives trade execution results from the EA (success/failure of commands).
Real wiring to TradeOrchestrator will be done in Wave 6.
"""
import logging

from fastapi import APIRouter, Depends

from app.dependencies import verify_auth_token
from app.models.requests import TradeResultPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trade", tags=["trade"])


@router.post("/result", dependencies=[Depends(verify_auth_token)])
async def receive_trade_result(payload: TradeResultPayload) -> dict:
    """Log trade result from the EA.

    Placeholder: logs the result and returns empty dict.
    Real wiring to TradeOrchestrator happens in Wave 6.
    """
    if payload.success:
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
