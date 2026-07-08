"""State Manager — FSM transition logic and business conditions.

Controls EA state transitions by validating against the FSM table and
evaluating business conditions per transition. Persists state in Redis
with a 120-second TTL.
"""
from datetime import datetime, timezone
from typing import Optional

from redis.asyncio import Redis

from app.config import Settings
from app.models.enums import EAState
from app.models.responses import TradeCommand, TransitionResponse
from app.services.position_manager import PositionManager
from app.services.risk_engine import RiskEngine
from app.services.signal_engine import SignalEngine
from app.services.trade_orchestrator import TradeOrchestrator


class StateManager:
    """FSM state transition controller.

    Args:
        redis: Async Redis client for state persistence.
        settings: Application settings with session hours.
        risk_engine: RiskEngine instance for risk status checks.
        signal_engine: SignalEngine instance for signal detection.
        trade_orchestrator: TradeOrchestrator instance for command construction.
        position_manager: PositionManager instance for position tracking.
    """

    # Valid FSM transitions as (from_state, to_state) pairs
    VALID_TRANSITIONS: set[tuple[str, str]] = {
        ("WAIT_SESSION", "CHECK_RISK"),
        ("CHECK_RISK", "SCAN_SIGNAL"),
        ("CHECK_RISK", "WAIT_SESSION"),
        ("SCAN_SIGNAL", "AI_CONFIRMATION"),
        ("SCAN_SIGNAL", "WAIT_SESSION"),
        ("AI_CONFIRMATION", "OPEN_POSITION"),
        ("AI_CONFIRMATION", "WAIT_SESSION"),
        ("OPEN_POSITION", "MANAGE_POSITION"),
        ("MANAGE_POSITION", "POSITION_CLOSED"),
        ("POSITION_CLOSED", "WAIT_SESSION"),
    }

    # Redis key for persisted EA state
    KEY_EA_STATE = "ea:state"
    # Redis key for trade result success flag
    KEY_TRADE_RESULT_SUCCESS = "trade:result:success"

    # TTL for state persistence in seconds
    STATE_TTL_SECONDS = 120

    def __init__(
        self,
        redis: Redis,
        settings: Settings,
        risk_engine: RiskEngine,
        signal_engine: SignalEngine,
        trade_orchestrator: TradeOrchestrator,
        position_manager: PositionManager,
    ) -> None:
        self._redis = redis
        self._settings = settings
        self._risk_engine = risk_engine
        self._signal_engine = signal_engine
        self._trade_orchestrator = trade_orchestrator
        self._position_manager = position_manager

    async def process_transition(
        self,
        current_state: str,
        requested_state: str,
        reason: str,
    ) -> TransitionResponse:
        """Process a state transition request.

        1. Validate transition is in FSM table
        2. Evaluate business conditions per transition
        3. Persist state in Redis (TTL 120s) if approved
        4. Return TransitionResponse

        Args:
            current_state: The EA's current state string.
            requested_state: The requested next state string.
            reason: Reason provided by EA for the transition.

        Returns:
            TransitionResponse with approval status and optional command.
        """
        # 1. Validate transition is in FSM table
        if (current_state, requested_state) not in self.VALID_TRANSITIONS:
            return TransitionResponse(
                approved=False,
                new_state=EAState(current_state),
                reason=f"Invalid transition: {current_state} -> {requested_state}",
            )

        # 2. Evaluate business conditions
        approved, reject_reason, command = self._evaluate_conditions(
            current_state, requested_state
        )

        # 3. Persist state in Redis if approved
        if approved:
            await self._persist_state(requested_state)
            new_state = EAState(requested_state)
        else:
            new_state = EAState(current_state)

        return TransitionResponse(
            approved=approved,
            new_state=new_state,
            command=command,
            reason=reject_reason,
        )

    def is_in_session(self, utc_now: datetime) -> bool:
        """Check if current UTC time is within trading session window.

        Returns True if hour is within London OR New York session.
        Per task spec: london_start_hour <= hour < ny_end_hour
        """
        hour = utc_now.hour
        in_london = self._settings.london_start_hour <= hour < self._settings.london_end_hour
        in_ny = self._settings.ny_start_hour <= hour < self._settings.ny_end_hour
        return in_london or in_ny

    async def get_current_state(self) -> Optional[str]:
        """Read current EA state from Redis. Returns None if missing (disconnected)."""
        value = await self._redis.get(self.KEY_EA_STATE)
        if value is None:
            return None
        return value if isinstance(value, str) else value.decode("utf-8")

    async def _evaluate_conditions(
        self,
        current_state: str,
        requested_state: str,
    ) -> tuple[bool, Optional[str], Optional[TradeCommand]]:
        """Evaluate business conditions for a specific transition.

        Returns:
            Tuple of (approved, reject_reason, trade_command).
        """
        utc_now = datetime.now(timezone.utc)

        # WAIT_SESSION → CHECK_RISK: must be in session
        if current_state == "WAIT_SESSION" and requested_state == "CHECK_RISK":
            if not self.is_in_session(utc_now):
                return False, "Outside trading session window", None
            return True, None, None

        # CHECK_RISK → SCAN_SIGNAL: risk must be CLEAR and in session
        if current_state == "CHECK_RISK" and requested_state == "SCAN_SIGNAL":
            if not self.is_in_session(utc_now):
                return False, "Outside trading session window", None
            status = await self._risk_engine.get_status()
            if status != "CLEAR":
                return False, "Risk status is RISK_LOCK", None
            return True, None, None

        # CHECK_RISK → WAIT_SESSION: always approve (fallback)
        if current_state == "CHECK_RISK" and requested_state == "WAIT_SESSION":
            return True, None, None

        # SCAN_SIGNAL → AI_CONFIRMATION: signal detected, construct TradeCommand
        if current_state == "SCAN_SIGNAL" and requested_state == "AI_CONFIRMATION":
            # Get signal from SignalEngine (synchronous method)
            signal = self._signal_engine.check_signal(
                candles=[],  # Will be provided by caller in real implementation
                current_tick=None,  # Will be provided by caller in real implementation
                utc_now=utc_now,
                has_open_position=await self._position_manager.has_open_position(),
                settings=self._settings,
            )
            if signal is not None:
                # Construct TradeCommand
                command = self._trade_orchestrator.construct_trade_command(signal)
                return True, None, command
            return False, "No signal detected", None

        # SCAN_SIGNAL → WAIT_SESSION: always approve (no signal found)
        if current_state == "SCAN_SIGNAL" and requested_state == "WAIT_SESSION":
            return True, None, None

        # AI_CONFIRMATION → OPEN_POSITION: always approve in MVP
        if current_state == "AI_CONFIRMATION" and requested_state == "OPEN_POSITION":
            return True, None, None

        # AI_CONFIRMATION → WAIT_SESSION: always approve (AI rejects)
        if current_state == "AI_CONFIRMATION" and requested_state == "WAIT_SESSION":
            return True, None, None

        # OPEN_POSITION → MANAGE_POSITION: check trade result success flag
        if current_state == "OPEN_POSITION" and requested_state == "MANAGE_POSITION":
            success_flag = await self._redis.get(self.KEY_TRADE_RESULT_SUCCESS)
            if success_flag is None or success_flag != "1":
                return False, "No successful trade result received", None
            # Clear the flag after consuming it
            await self._redis.delete(self.KEY_TRADE_RESULT_SUCCESS)
            return True, None, None

        # MANAGE_POSITION → POSITION_CLOSED: record P&L and always approve
        if current_state == "MANAGE_POSITION" and requested_state == "POSITION_CLOSED":
            # Retrieve trade result to get P&L (simplified for MVP)
            # In real implementation, this would fetch the actual P&L from the trade result
            pnl = 0.0  # Placeholder - would be retrieved from actual trade execution
            await self._risk_engine.record_trade_pnl(pnl)
            return True, None, None

        # POSITION_CLOSED → WAIT_SESSION: always approve
        if current_state == "POSITION_CLOSED" and requested_state == "WAIT_SESSION":
            return True, None, None

        # Fallback: should not reach here if VALID_TRANSITIONS is correct
        return False, "Unhandled transition condition", None

    async def _persist_state(self, state: str) -> None:
        """Persist the new state in Redis with TTL."""
        await self._redis.set(
            self.KEY_EA_STATE,
            state,
            ex=self.STATE_TTL_SECONDS,
        )
