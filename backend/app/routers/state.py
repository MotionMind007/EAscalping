"""State management router — transition requests and recovery.

Handles EA state transition requests (FSM control) and recovery after
disconnect/restart events. The real StateManager business logic is wired
in Wave 3; this wave provides placeholder implementations that approve
all valid transitions.
"""
import logging

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.dependencies import get_redis, verify_auth_token
from app.models.enums import EAState
from app.models.requests import RecoveryPayload, TransitionRequest
from app.models.responses import RecoveryResponse, TransitionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/state", tags=["state"])

# Valid FSM transitions (from design doc)
VALID_TRANSITIONS: set[tuple[str, str]] = {
    (EAState.BOOT, EAState.CONNECT),
    (EAState.CONNECT, EAState.WAIT_SESSION),
    (EAState.WAIT_SESSION, EAState.CHECK_RISK),
    (EAState.CHECK_RISK, EAState.SCAN_SIGNAL),
    (EAState.CHECK_RISK, EAState.WAIT_SESSION),
    (EAState.SCAN_SIGNAL, EAState.AI_CONFIRMATION),
    (EAState.SCAN_SIGNAL, EAState.WAIT_SESSION),
    (EAState.AI_CONFIRMATION, EAState.OPEN_POSITION),
    (EAState.AI_CONFIRMATION, EAState.WAIT_SESSION),
    (EAState.OPEN_POSITION, EAState.MANAGE_POSITION),
    (EAState.MANAGE_POSITION, EAState.POSITION_CLOSED),
    (EAState.POSITION_CLOSED, EAState.WAIT_SESSION),
}


@router.post("/transition", dependencies=[Depends(verify_auth_token)])
async def state_transition(
    payload: TransitionRequest,
    redis: Redis = Depends(get_redis),
) -> TransitionResponse:
    """Process EA state transition request.

    Uses StateManager service to evaluate business conditions for
    each transition. Dependencies are injected via factory pattern.
    """
    current = payload.current_state.value
    requested = payload.requested_state.value

    # Get settings and create services
    from app.config import Settings
    from app.services.position_manager import PositionManager
    from app.services.risk_engine import RiskEngine
    from app.services.signal_engine import SignalEngine
    from app.services.state_manager import StateManager
    from app.services.trade_orchestrator import TradeOrchestrator

    settings = Settings()
    risk_engine = RiskEngine(redis, settings)
    signal_engine = SignalEngine()
    trade_orchestrator = TradeOrchestrator(redis, settings)
    position_manager = PositionManager(redis)
    state_manager = StateManager(
        redis=redis,
        settings=settings,
        risk_engine=risk_engine,
        signal_engine=signal_engine,
        trade_orchestrator=trade_orchestrator,
        position_manager=position_manager,
    )

    # Process transition through StateManager
    response = await state_manager.process_transition(
        current_state=current,
        requested_state=requested,
        reason=payload.reason,
    )

    logger.info(
        "Transition %s -> %s: approved=%s, reason=%s",
        current, requested, response.approved, response.reason or "N/A"
    )
    return response


@router.post("/recovery", dependencies=[Depends(verify_auth_token)])
async def state_recovery(
    payload: RecoveryPayload,
    redis: Redis = Depends(get_redis),
) -> RecoveryResponse:
    """Reconcile backend state with EA-reported state after recovery.

    Placeholder implementation: confirms the EA's reported state.
    Full reconciliation (position matching, command replay) is wired in Wave 6.
    """
    # Store the recovered state in Redis
    await redis.set("ea:state", payload.current_state.value, ex=120)

    logger.info(
        "Recovery: confirmed state=%s, equity=%.2f, has_position=%s",
        payload.current_state.value,
        payload.account_equity,
        payload.open_position is not None,
    )

    return RecoveryResponse(
        confirmed_state=payload.current_state,
        pending_commands=[],
    )
