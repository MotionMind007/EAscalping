"""Unit tests for TradeOrchestrator service."""
import json

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from app.models.enums import CommandType
from app.services.signal_engine import Signal
from app.services.trade_orchestrator import TradeOrchestrator


@pytest.fixture
def mock_settings():
    """Settings mock with default trading parameters."""
    settings = MagicMock()
    settings.lot_size = 0.10
    settings.stop_loss_points = 100
    settings.take_profit_points = 150
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
def orchestrator(mock_redis, mock_settings):
    """TradeOrchestrator instance with mocked dependencies."""
    return TradeOrchestrator(redis=mock_redis, settings=mock_settings)


class TestConstructTradeCommand:
    """Tests for TradeOrchestrator.construct_trade_command()."""

    def test_buy_signal_produces_buy_command(self, orchestrator):
        """BUY signal produces a BUY command."""
        signal = Signal(
            direction="BUY",
            entry_price=2000.00,
            stop_loss=1999.00,
            take_profit=2001.50,
        )
        command = orchestrator.construct_trade_command(signal)

        assert command.type == CommandType.BUY

    def test_sell_signal_produces_sell_command(self, orchestrator):
        """SELL signal produces a SELL command."""
        signal = Signal(
            direction="SELL",
            entry_price=2000.00,
            stop_loss=2001.00,
            take_profit=1998.50,
        )
        command = orchestrator.construct_trade_command(signal)

        assert command.type == CommandType.SELL

    def test_lot_size_always_equals_settings(self, orchestrator, mock_settings):
        """Lot size invariant: always equals settings.lot_size."""
        signal = Signal(
            direction="BUY",
            entry_price=2500.00,
            stop_loss=2499.00,
            take_profit=2501.50,
        )
        command = orchestrator.construct_trade_command(signal)

        assert command.lot_size == mock_settings.lot_size

    def test_lot_size_with_different_settings(self, mock_redis):
        """Lot size follows settings even when changed."""
        settings = MagicMock()
        settings.lot_size = 0.50
        orch = TradeOrchestrator(redis=mock_redis, settings=settings)

        signal = Signal(
            direction="BUY",
            entry_price=2000.00,
            stop_loss=1999.00,
            take_profit=2001.50,
        )
        command = orch.construct_trade_command(signal)

        assert command.lot_size == 0.50

    def test_stop_loss_from_signal(self, orchestrator):
        """Stop loss comes from the signal."""
        signal = Signal(
            direction="BUY",
            entry_price=2000.00,
            stop_loss=1999.00,
            take_profit=2001.50,
        )
        command = orchestrator.construct_trade_command(signal)

        assert command.stop_loss == 1999.00

    def test_take_profit_from_signal(self, orchestrator):
        """Take profit comes from the signal."""
        signal = Signal(
            direction="BUY",
            entry_price=2000.00,
            stop_loss=1999.00,
            take_profit=2001.50,
        )
        command = orchestrator.construct_trade_command(signal)

        assert command.take_profit == 2001.50


class TestRecordPendingTrade:
    """Tests for TradeOrchestrator.record_pending_trade()."""

    @pytest.mark.asyncio
    async def test_stores_pending_trade_in_redis(self, orchestrator, mock_redis):
        """Pending trade is stored in Redis with correct structure."""
        from app.models.responses import TradeCommand

        command = TradeCommand(
            type=CommandType.BUY,
            lot_size=0.10,
            stop_loss=1999.00,
            take_profit=2001.50,
        )
        await orchestrator.record_pending_trade(command)

        raw = mock_redis._store.get("trade:pending")
        assert raw is not None
        data = json.loads(raw)
        assert data["type"] == "BUY"
        assert data["lot_size"] == 0.10
        assert data["stop_loss"] == 1999.00
        assert data["take_profit"] == 2001.50
        assert data["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_stores_sell_command(self, orchestrator, mock_redis):
        """SELL command stored correctly."""
        from app.models.responses import TradeCommand

        command = TradeCommand(
            type=CommandType.SELL,
            lot_size=0.10,
            stop_loss=2001.00,
            take_profit=1998.50,
        )
        await orchestrator.record_pending_trade(command)

        raw = mock_redis._store.get("trade:pending")
        data = json.loads(raw)
        assert data["type"] == "SELL"


class TestRecordTradeResult:
    """Tests for TradeOrchestrator.record_trade_result()."""

    @pytest.mark.asyncio
    async def test_success_sets_flag_and_clears_pending(self, orchestrator, mock_redis):
        """Success sets trade:result:success and clears pending."""
        mock_redis._store["trade:pending"] = '{"status": "PENDING"}'

        await orchestrator.record_trade_result(
            success=True, ticket=12345, fill_price=2000.05
        )

        assert mock_redis._store.get("trade:result:success") == "1"
        assert "trade:pending" not in mock_redis._store

    @pytest.mark.asyncio
    async def test_failure_removes_success_flag(self, orchestrator, mock_redis):
        """Failure removes any existing success flag."""
        mock_redis._store["trade:result:success"] = "1"
        mock_redis._store["trade:pending"] = '{"status": "PENDING"}'

        await orchestrator.record_trade_result(
            success=False, error_code=10006
        )

        assert "trade:result:success" not in mock_redis._store
        assert "trade:pending" not in mock_redis._store

    @pytest.mark.asyncio
    async def test_clears_pending_on_success(self, orchestrator, mock_redis):
        """Pending trade is cleared on successful result."""
        mock_redis._store["trade:pending"] = '{"status": "PENDING"}'

        await orchestrator.record_trade_result(success=True, ticket=100)

        assert "trade:pending" not in mock_redis._store

    @pytest.mark.asyncio
    async def test_clears_pending_on_failure(self, orchestrator, mock_redis):
        """Pending trade is cleared on failed result."""
        mock_redis._store["trade:pending"] = '{"status": "PENDING"}'

        await orchestrator.record_trade_result(success=False, error_code=999)

        assert "trade:pending" not in mock_redis._store
