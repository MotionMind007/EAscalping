"""Unit tests for RiskEngine service."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.risk_engine import RiskEngine


@pytest.fixture
def mock_settings():
    """Settings mock with default max_daily_loss_pct=3.0."""
    settings = MagicMock()
    settings.max_daily_loss_pct = 3.0
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


@pytest_asyncio.fixture
async def risk_engine(mock_redis, mock_settings):
    """RiskEngine instance with mocked dependencies."""
    return RiskEngine(redis=mock_redis, settings=mock_settings)


class TestGetStatus:
    """Tests for RiskEngine.get_status()."""

    @pytest.mark.asyncio
    async def test_returns_clear_when_no_lock(self, risk_engine, mock_redis):
        """Status is CLEAR when risk:lock key does not exist."""
        result = await risk_engine.get_status()
        assert result == "CLEAR"

    @pytest.mark.asyncio
    async def test_returns_risk_lock_when_locked(self, risk_engine, mock_redis):
        """Status is RISK_LOCK when risk:lock is '1'."""
        mock_redis._store["risk:lock"] = "1"
        result = await risk_engine.get_status()
        assert result == "RISK_LOCK"

    @pytest.mark.asyncio
    async def test_returns_clear_when_lock_value_not_one(self, risk_engine, mock_redis):
        """Status is CLEAR when risk:lock exists but is not '1'."""
        mock_redis._store["risk:lock"] = "0"
        result = await risk_engine.get_status()
        assert result == "CLEAR"


class TestRecordTradePnl:
    """Tests for RiskEngine.record_trade_pnl()."""

    @pytest.mark.asyncio
    async def test_accumulates_profit(self, risk_engine, mock_redis):
        """P/L accumulates correctly with positive values."""
        mock_redis._store["risk:daily_pnl"] = "100.0"
        mock_redis._store["risk:starting_equity"] = "10000.0"

        await risk_engine.record_trade_pnl(50.0)

        assert mock_redis._store["risk:daily_pnl"] == "150.0"

    @pytest.mark.asyncio
    async def test_accumulates_loss(self, risk_engine, mock_redis):
        """P/L accumulates correctly with negative values."""
        mock_redis._store["risk:daily_pnl"] = "0.0"
        mock_redis._store["risk:starting_equity"] = "10000.0"

        await risk_engine.record_trade_pnl(-100.0)

        assert mock_redis._store["risk:daily_pnl"] == "-100.0"

    @pytest.mark.asyncio
    async def test_activates_lock_at_threshold(self, risk_engine, mock_redis):
        """RISK_LOCK activates when loss >= 3% of starting equity."""
        mock_redis._store["risk:daily_pnl"] = "0.0"
        mock_redis._store["risk:starting_equity"] = "10000.0"

        # -300 is exactly 3% of 10000
        await risk_engine.record_trade_pnl(-300.0)

        assert mock_redis._store.get("risk:lock") == "1"

    @pytest.mark.asyncio
    async def test_does_not_activate_lock_below_threshold(self, risk_engine, mock_redis):
        """RISK_LOCK does not activate when loss < 3%."""
        mock_redis._store["risk:daily_pnl"] = "0.0"
        mock_redis._store["risk:starting_equity"] = "10000.0"

        await risk_engine.record_trade_pnl(-299.99)

        assert "risk:lock" not in mock_redis._store

    @pytest.mark.asyncio
    async def test_starts_from_zero_when_no_pnl_key(self, risk_engine, mock_redis):
        """Starts from 0 if risk:daily_pnl key doesn't exist."""
        mock_redis._store["risk:starting_equity"] = "10000.0"

        await risk_engine.record_trade_pnl(50.0)

        assert mock_redis._store["risk:daily_pnl"] == "50.0"


class TestResetDaily:
    """Tests for RiskEngine.reset_daily()."""

    @pytest.mark.asyncio
    async def test_resets_all_keys(self, risk_engine, mock_redis):
        """reset_daily clears lock, zeros pnl, sets new equity."""
        mock_redis._store["risk:lock"] = "1"
        mock_redis._store["risk:daily_pnl"] = "-500.0"
        mock_redis._store["risk:starting_equity"] = "9500.0"

        await risk_engine.reset_daily(9800.0)

        assert "risk:lock" not in mock_redis._store
        assert mock_redis._store["risk:daily_pnl"] == "0.0"
        assert mock_redis._store["risk:starting_equity"] == "9800.0"


class TestCalculateLossPct:
    """Tests for RiskEngine.calculate_loss_pct() — pure function."""

    def test_positive_pnl_returns_zero(self, risk_engine):
        """No loss percentage when P/L is positive."""
        assert risk_engine.calculate_loss_pct(100.0, 10000.0) == 0.0

    def test_zero_pnl_returns_zero(self, risk_engine):
        """No loss percentage when P/L is zero."""
        assert risk_engine.calculate_loss_pct(0.0, 10000.0) == 0.0

    def test_negative_pnl_calculates_correctly(self, risk_engine):
        """Loss percentage calculated correctly for negative P/L."""
        # -300 / 10000 * 100 = 3.0%
        assert risk_engine.calculate_loss_pct(-300.0, 10000.0) == 3.0

    def test_zero_equity_returns_zero(self, risk_engine):
        """Returns 0 if starting equity is 0 (division guard)."""
        assert risk_engine.calculate_loss_pct(-100.0, 0.0) == 0.0

    def test_large_loss(self, risk_engine):
        """Handles large losses correctly."""
        # -5000 / 10000 * 100 = 50.0%
        assert risk_engine.calculate_loss_pct(-5000.0, 10000.0) == 50.0


class TestInitialize:
    """Tests for RiskEngine.initialize()."""

    @pytest.mark.asyncio
    async def test_sets_equity_when_not_exists(self, risk_engine, mock_redis):
        """Sets starting equity and zeros P/L on fresh start."""
        await risk_engine.initialize(15000.0)

        assert mock_redis._store["risk:starting_equity"] == "15000.0"
        assert mock_redis._store["risk:daily_pnl"] == "0.0"

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing(self, risk_engine, mock_redis):
        """Does not overwrite existing equity (mid-day restart)."""
        mock_redis._store["risk:starting_equity"] = "12000.0"

        await risk_engine.initialize(15000.0)

        assert mock_redis._store["risk:starting_equity"] == "12000.0"


class TestGetDailyPnl:
    """Tests for RiskEngine.get_daily_pnl()."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_not_set(self, risk_engine):
        """Returns 0.0 when no daily P/L key exists."""
        result = await risk_engine.get_daily_pnl()
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_returns_stored_value(self, risk_engine, mock_redis):
        """Returns the stored float value."""
        mock_redis._store["risk:daily_pnl"] = "123.45"
        result = await risk_engine.get_daily_pnl()
        assert result == 123.45


class TestGetStartingEquity:
    """Tests for RiskEngine.get_starting_equity()."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_not_set(self, risk_engine):
        """Returns 0.0 when no starting equity key exists."""
        result = await risk_engine.get_starting_equity()
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_returns_stored_value(self, risk_engine, mock_redis):
        """Returns the stored float value."""
        mock_redis._store["risk:starting_equity"] = "50000.0"
        result = await risk_engine.get_starting_equity()
        assert result == 50000.0
