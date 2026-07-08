"""Unit tests for StateManager service."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.enums import EAState
from app.services.state_manager import StateManager


@pytest.fixture
def mock_settings():
    """Settings mock with default session hours."""
    settings = MagicMock()
    settings.london_start_hour = 8
    settings.london_end_hour = 16
    settings.ny_start_hour = 13
    settings.ny_end_hour = 21
    return settings


@pytest.fixture
def mock_redis():
    """Async Redis mock with get/set/delete."""
    redis = AsyncMock()
    redis._store = {}

    async def _get(key):
        return redis._store.get(key)

    async def _set(key, value, *args, **kwargs):
        redis._store[key] = value

    async def _delete(key):
        redis._store.pop(key, None)

    redis.get = AsyncMock(side_effect=_get)
    redis.set = AsyncMock(side_effect=_set)
    redis.delete = AsyncMock(side_effect=_delete)
    return redis


@pytest.fixture
def mock_risk_engine():
    """Mocked RiskEngine."""
    engine = AsyncMock()
    engine.get_status = AsyncMock(return_value="CLEAR")
    return engine


@pytest.fixture
def mock_position_manager():
    """Mocked PositionManager."""
    manager = AsyncMock()
    manager.has_open_position = AsyncMock(return_value=False)
    return manager


@pytest_asyncio.fixture
async def state_manager(mock_redis, mock_settings, mock_risk_engine, mock_signal_engine, mock_trade_orchestrator, mock_position_manager):
    """StateManager with mocked dependencies."""
    return StateManager(
        redis=mock_redis,
        settings=mock_settings,
        risk_engine=mock_risk_engine,
        signal_engine=mock_signal_engine,
        trade_orchestrator=mock_trade_orchestrator,
        position_manager=mock_position_manager,
    )


class TestValidTransitions:
    """Tests for FSM transition validation."""

    @pytest.mark.asyncio
    async def test_invalid_transition_rejected(self, state_manager):
        """Invalid transitions are rejected with reason."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "WAIT_SESSION", "OPEN_POSITION", "skip ahead"
            )
        assert result.approved is False
        assert result.new_state == EAState.WAIT_SESSION
        assert "Invalid transition" in result.reason

    @pytest.mark.asyncio
    async def test_all_valid_transitions_in_table(self, state_manager):
        """Verify all 10 transitions are defined in the table."""
        assert len(StateManager.VALID_TRANSITIONS) == 10

    @pytest.mark.asyncio
    async def test_transition_backwards_rejected(self, state_manager):
        """Backward transitions not in the table are rejected."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "SCAN_SIGNAL", "CHECK_RISK", "go back"
            )
        assert result.approved is False


class TestIsInSession:
    """Tests for StateManager.is_in_session()."""

    def test_in_london_session(self, state_manager):
        """Hour 10 is in London session (8-16)."""
        utc_now = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        assert state_manager.is_in_session(utc_now) is True

    def test_in_ny_session(self, state_manager):
        """Hour 18 is in NY session (13-21)."""
        utc_now = datetime(2024, 1, 1, 18, 0, 0, tzinfo=timezone.utc)
        assert state_manager.is_in_session(utc_now) is True

    def test_in_overlap_session(self, state_manager):
        """Hour 14 is in both London and NY overlap."""
        utc_now = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        assert state_manager.is_in_session(utc_now) is True

    def test_outside_session(self, state_manager):
        """Hour 5 is outside all sessions."""
        utc_now = datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc)
        assert state_manager.is_in_session(utc_now) is False

    def test_exactly_at_london_start(self, state_manager):
        """Hour 8 is the start of London session (inclusive)."""
        utc_now = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        assert state_manager.is_in_session(utc_now) is True

    def test_exactly_at_ny_end(self, state_manager):
        """Hour 21 is the end of NY session (exclusive)."""
        utc_now = datetime(2024, 1, 1, 21, 0, 0, tzinfo=timezone.utc)
        assert state_manager.is_in_session(utc_now) is False


class TestWaitSessionToCheckRisk:
    """Tests for WAIT_SESSION → CHECK_RISK transition."""

    @pytest.mark.asyncio
    async def test_approved_in_session(self, state_manager, mock_redis):
        """Approved when within trading session."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "WAIT_SESSION", "CHECK_RISK", "session active"
            )
        assert result.approved is True
        assert result.new_state == EAState.CHECK_RISK
        assert mock_redis._store.get("ea:state") == "CHECK_RISK"

    @pytest.mark.asyncio
    async def test_rejected_outside_session(self, state_manager, mock_redis):
        """Rejected when outside trading session."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "WAIT_SESSION", "CHECK_RISK", "try session"
            )
        assert result.approved is False
        assert result.new_state == EAState.WAIT_SESSION
        assert "session" in result.reason.lower()


class TestCheckRiskToScanSignal:
    """Tests for CHECK_RISK → SCAN_SIGNAL transition."""

    @pytest.mark.asyncio
    async def test_approved_when_clear_and_in_session(
        self, state_manager, mock_risk_engine
    ):
        """Approved when risk is CLEAR and in session."""
        mock_risk_engine.get_status.return_value = "CLEAR"
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "CHECK_RISK", "SCAN_SIGNAL", "risk check"
            )
        assert result.approved is True
        assert result.new_state == EAState.SCAN_SIGNAL

    @pytest.mark.asyncio
    async def test_rejected_when_risk_locked(
        self, state_manager, mock_risk_engine
    ):
        """Rejected when risk status is RISK_LOCK."""
        mock_risk_engine.get_status.return_value = "RISK_LOCK"
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "CHECK_RISK", "SCAN_SIGNAL", "risk check"
            )
        assert result.approved is False
        assert "RISK_LOCK" in result.reason

    @pytest.mark.asyncio
    async def test_rejected_when_outside_session(
        self, state_manager, mock_risk_engine
    ):
        """Rejected when outside session even if risk is CLEAR."""
        mock_risk_engine.get_status.return_value = "CLEAR"
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "CHECK_RISK", "SCAN_SIGNAL", "risk check"
            )
        assert result.approved is False
        assert "session" in result.reason.lower()


class TestOpenPositionToManagePosition:
    """Tests for OPEN_POSITION → MANAGE_POSITION transition."""

    @pytest.mark.asyncio
    async def test_approved_with_success_flag(self, state_manager, mock_redis):
        """Approved when trade:result:success flag is set."""
        mock_redis._store["trade:result:success"] = "1"
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "OPEN_POSITION", "MANAGE_POSITION", "trade success"
            )
        assert result.approved is True
        assert result.new_state == EAState.MANAGE_POSITION
        # Flag should be consumed
        assert "trade:result:success" not in mock_redis._store

    @pytest.mark.asyncio
    async def test_rejected_without_success_flag(self, state_manager, mock_redis):
        """Rejected when no trade result success flag."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "OPEN_POSITION", "MANAGE_POSITION", "waiting"
            )
        assert result.approved is False
        assert "trade result" in result.reason.lower()


class TestAlwaysApprovedTransitions:
    """Tests for transitions that always approve."""

    @pytest.mark.asyncio
    async def test_manage_to_position_closed(self, state_manager):
        """MANAGE_POSITION → POSITION_CLOSED always approves."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "MANAGE_POSITION", "POSITION_CLOSED", "position closed by SL"
            )
        assert result.approved is True
        assert result.new_state == EAState.POSITION_CLOSED

    @pytest.mark.asyncio
    async def test_position_closed_to_wait_session(self, state_manager):
        """POSITION_CLOSED → WAIT_SESSION always approves."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "POSITION_CLOSED", "WAIT_SESSION", "cycle complete"
            )
        assert result.approved is True
        assert result.new_state == EAState.WAIT_SESSION

    @pytest.mark.asyncio
    async def test_ai_confirmation_to_open_position(self, state_manager):
        """AI_CONFIRMATION → OPEN_POSITION always approves in MVP."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "AI_CONFIRMATION", "OPEN_POSITION", "AI confirms"
            )
        assert result.approved is True
        assert result.new_state == EAState.OPEN_POSITION

    @pytest.mark.asyncio
    async def test_scan_signal_to_ai_confirmation(self, state_manager):
        """SCAN_SIGNAL → AI_CONFIRMATION approves in MVP."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await state_manager.process_transition(
                "SCAN_SIGNAL", "AI_CONFIRMATION", "signal detected"
            )
        assert result.approved is True
        assert result.new_state == EAState.AI_CONFIRMATION


class TestStatePersistence:
    """Tests for Redis state persistence."""

    @pytest.mark.asyncio
    async def test_state_persisted_on_approval(self, state_manager, mock_redis):
        """State is saved to Redis on approved transition."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await state_manager.process_transition(
                "MANAGE_POSITION", "POSITION_CLOSED", "closed"
            )
        assert mock_redis._store.get("ea:state") == "POSITION_CLOSED"

    @pytest.mark.asyncio
    async def test_state_not_persisted_on_rejection(self, state_manager, mock_redis):
        """State is NOT saved to Redis on rejected transition."""
        with patch(
            "app.services.state_manager.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await state_manager.process_transition(
                "WAIT_SESSION", "CHECK_RISK", "try session"
            )
        assert "ea:state" not in mock_redis._store


class TestGetCurrentState:
    """Tests for StateManager.get_current_state()."""

    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self, state_manager):
        """Returns None when no state in Redis (disconnected)."""
        result = await state_manager.get_current_state()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_stored_state(self, state_manager, mock_redis):
        """Returns the stored state string."""
        mock_redis._store["ea:state"] = "SCAN_SIGNAL"
        result = await state_manager.get_current_state()
        assert result == "SCAN_SIGNAL"
