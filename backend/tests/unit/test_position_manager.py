"""Unit tests for PositionManager service."""
import json

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from app.models.enums import CommandType, Direction
from app.models.requests import OrphanPayload, PositionStatusPayload
from app.services.position_manager import PositionManager


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
def position_manager(mock_redis):
    """PositionManager instance with mocked Redis."""
    return PositionManager(redis=mock_redis)


class TestGetKnownTickets:
    """Tests for PositionManager.get_known_tickets()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_position(self, position_manager):
        """Returns empty list when no position is tracked."""
        tickets = await position_manager.get_known_tickets()
        assert tickets == []

    @pytest.mark.asyncio
    async def test_returns_ticket_when_position_exists(self, position_manager, mock_redis):
        """Returns the tracked ticket number."""
        mock_redis._store["position:open"] = json.dumps({
            "ticket": 12345,
            "direction": "BUY",
            "lot_size": 0.10,
            "open_price": 2000.00,
        })

        tickets = await position_manager.get_known_tickets()

        assert tickets == [12345]

    @pytest.mark.asyncio
    async def test_returns_empty_when_ticket_is_none(self, position_manager, mock_redis):
        """Returns empty list if stored data has no ticket field."""
        mock_redis._store["position:open"] = json.dumps({
            "direction": "BUY",
            "lot_size": 0.10,
        })

        tickets = await position_manager.get_known_tickets()

        assert tickets == []


class TestHasOpenPosition:
    """Tests for PositionManager.has_open_position()."""

    @pytest.mark.asyncio
    async def test_false_when_no_position(self, position_manager):
        """Returns False when no position exists."""
        result = await position_manager.has_open_position()
        assert result is False

    @pytest.mark.asyncio
    async def test_true_when_position_exists(self, position_manager, mock_redis):
        """Returns True when a position is tracked."""
        mock_redis._store["position:open"] = json.dumps({
            "ticket": 100,
            "direction": "BUY",
        })

        result = await position_manager.has_open_position()

        assert result is True


class TestRecordOpenPosition:
    """Tests for PositionManager.record_open_position()."""

    @pytest.mark.asyncio
    async def test_stores_position_data(self, position_manager, mock_redis):
        """Records position details in Redis."""
        await position_manager.record_open_position(
            ticket=54321,
            direction="SELL",
            lot_size=0.20,
            open_price=1995.50,
        )

        raw = mock_redis._store.get("position:open")
        assert raw is not None
        data = json.loads(raw)
        assert data["ticket"] == 54321
        assert data["direction"] == "SELL"
        assert data["lot_size"] == 0.20
        assert data["open_price"] == 1995.50

    @pytest.mark.asyncio
    async def test_overwrites_previous_position(self, position_manager, mock_redis):
        """New position overwrites the previous one."""
        mock_redis._store["position:open"] = json.dumps({"ticket": 111})

        await position_manager.record_open_position(
            ticket=222, direction="BUY", lot_size=0.10, open_price=2000.00
        )

        data = json.loads(mock_redis._store["position:open"])
        assert data["ticket"] == 222


class TestUpdatePositionStatus:
    """Tests for PositionManager.update_position_status()."""

    @pytest.mark.asyncio
    async def test_updates_with_current_data(self, position_manager, mock_redis):
        """Updates position with current price and unrealized P/L."""
        payload = PositionStatusPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction=Direction.BUY,
            lot_size=0.10,
            open_price=2000.00,
            current_price=2005.00,
            unrealized_pnl=50.0,
            timestamp="2024-01-15T10:30:00Z",
        )

        await position_manager.update_position_status(payload)

        raw = mock_redis._store.get("position:open")
        assert raw is not None
        data = json.loads(raw)
        assert data["ticket"] == 12345
        assert data["symbol"] == "XAUUSD"
        assert data["direction"] == "BUY"
        assert data["lot_size"] == 0.10
        assert data["open_price"] == 2000.00
        assert data["current_price"] == 2005.00
        assert data["unrealized_pnl"] == 50.0
        assert data["timestamp"] == "2024-01-15T10:30:00Z"


class TestMarkPositionClosed:
    """Tests for PositionManager.mark_position_closed()."""

    @pytest.mark.asyncio
    async def test_removes_position_from_redis(self, position_manager, mock_redis):
        """Closed position removes the Redis key."""
        mock_redis._store["position:open"] = json.dumps({"ticket": 999})

        await position_manager.mark_position_closed()

        assert "position:open" not in mock_redis._store

    @pytest.mark.asyncio
    async def test_no_error_when_no_position(self, position_manager):
        """Closing when no position exists does not error."""
        await position_manager.mark_position_closed()
        # No exception means success


class TestHandleOrphan:
    """Tests for PositionManager.handle_orphan()."""

    @pytest.mark.asyncio
    async def test_returns_close_command(self, position_manager):
        """Returns a CLOSE command for the orphan ticket."""
        orphan = OrphanPayload(
            ticket=77777,
            symbol="XAUUSD",
            direction=Direction.BUY,
            lot_size=0.15,
            open_price=1990.00,
            open_time="2024-01-15T08:00:00Z",
        )

        command = await position_manager.handle_orphan(orphan)

        assert command.type == CommandType.CLOSE
        assert command.ticket == 77777
        assert command.lot_size == 0.15

    @pytest.mark.asyncio
    async def test_close_command_has_placeholder_sl_tp(self, position_manager):
        """CLOSE command has placeholder SL/TP (not used for closes)."""
        orphan = OrphanPayload(
            ticket=88888,
            symbol="XAUUSD",
            direction=Direction.SELL,
            lot_size=0.10,
            open_price=2010.00,
            open_time="2024-01-15T09:00:00Z",
        )

        command = await position_manager.handle_orphan(orphan)

        assert command.stop_loss == 0.01
        assert command.take_profit == 0.01

    @pytest.mark.asyncio
    async def test_uses_orphan_lot_size(self, position_manager):
        """CLOSE command uses the orphan's lot_size, not settings."""
        orphan = OrphanPayload(
            ticket=99999,
            symbol="XAUUSD",
            direction=Direction.BUY,
            lot_size=0.50,
            open_price=2020.00,
            open_time="2024-01-15T10:00:00Z",
        )

        command = await position_manager.handle_orphan(orphan)

        assert command.lot_size == 0.50
