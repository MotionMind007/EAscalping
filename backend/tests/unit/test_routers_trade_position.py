"""Unit tests for trade and position routers (Tasks 3.6, 3.7).

Uses FastAPI TestClient with mocked Redis dependency to test endpoint
validation, auth, and response structure without requiring real services.
"""
import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_redis, verify_auth_token
from app.main import app

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client for dependency injection."""
    redis = AsyncMock()
    redis.set = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def client(mock_redis):
    """Create async test client with mocked dependencies."""
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[verify_auth_token] = lambda: None
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    """Create async test client WITHOUT auth override (to test 401)."""
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("AUTH_TOKEN", "test-token-secret")
    from app.dependencies import get_settings
    get_settings.cache_clear()

    mock_redis = AsyncMock()
    app.dependency_overrides[get_redis] = lambda: mock_redis
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()


# ─── Trade Router Tests ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestTradeRouter:
    """Tests for POST /api/v1/trade/result."""

    async def test_trade_result_success(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "success": True,
                "ticket": 12345,
                "fill_price": 2025.50,
                "command_type": "BUY",
                "slippage_points": 2,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/trade/result", json=payload)
        assert response.status_code == 200
        assert response.json() == {}

    async def test_trade_result_failure(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "success": False,
                "error_code": 10006,
                "error_message": "No connection",
                "command_type": "BUY",
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/trade/result", json=payload)
        assert response.status_code == 200
        assert response.json() == {}

    async def test_trade_result_invalid_command_type(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "success": True,
                "ticket": 12345,
                "fill_price": 2025.50,
                "command_type": "INVALID",
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/trade/result", json=payload)
        assert response.status_code == 422

    async def test_trade_result_missing_command_type(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "success": True,
                "ticket": 12345,
                "fill_price": 2025.50,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/trade/result", json=payload)
        assert response.status_code == 422

    async def test_trade_result_requires_auth(self, unauth_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "success": True,
                "ticket": 12345,
                "fill_price": 2025.50,
                "command_type": "BUY",
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/trade/result", json=payload)
        assert response.status_code == 401


# ─── Position Router Tests ────────────────────────────────────────────────────


@pytest.mark.unit
class TestPositionStatusRouter:
    """Tests for POST /api/v1/position/status."""

    async def test_position_status_valid(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "ticket": 12345,
                "symbol": "XAUUSD",
                "direction": "BUY",
                "lot_size": 0.10,
                "open_price": 2025.50,
                "current_price": 2026.00,
                "unrealized_pnl": 5.00,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/position/status", json=payload)
        assert response.status_code == 200
        assert response.json() == {}
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "position:open"
        stored = json.loads(call_args[0][1])
        assert stored["ticket"] == 12345
        assert stored["symbol"] == "XAUUSD"
        assert stored["direction"] == "BUY"

    async def test_position_status_invalid_direction(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "ticket": 12345,
                "symbol": "XAUUSD",
                "direction": "HOLD",
                "lot_size": 0.10,
                "open_price": 2025.50,
                "current_price": 2026.00,
                "unrealized_pnl": 5.00,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/position/status", json=payload)
        assert response.status_code == 422

    async def test_position_status_requires_auth(self, unauth_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "ticket": 12345,
                "symbol": "XAUUSD",
                "direction": "BUY",
                "lot_size": 0.10,
                "open_price": 2025.50,
                "current_price": 2026.00,
                "unrealized_pnl": 5.00,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/position/status", json=payload)
        assert response.status_code == 401


@pytest.mark.unit
class TestPositionKnownRouter:
    """Tests for POST /api/v1/position/known."""

    async def test_known_with_open_position(self, client, mock_redis):
        mock_redis.get.return_value = json.dumps({
            "ticket": 12345,
            "symbol": "XAUUSD",
            "direction": "BUY",
            "lot_size": 0.10,
        })
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {"symbol": "XAUUSD"}
            response = await ac.post("/api/v1/position/known", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tickets"] == [12345]

    async def test_known_no_open_position(self, client, mock_redis):
        mock_redis.get.return_value = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {"symbol": "XAUUSD"}
            response = await ac.post("/api/v1/position/known", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tickets"] == []

    async def test_known_requires_auth(self, unauth_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {"symbol": "XAUUSD"}
            response = await ac.post("/api/v1/position/known", json=payload)
        assert response.status_code == 401


@pytest.mark.unit
class TestPositionOrphanRouter:
    """Tests for POST /api/v1/position/orphan."""

    async def test_orphan_returns_close_command(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "ticket": 99999,
                "symbol": "XAUUSD",
                "direction": "SELL",
                "lot_size": 0.10,
                "open_price": 2030.00,
                "open_time": "2024-01-15T09:00:00Z",
            }
            response = await ac.post("/api/v1/position/orphan", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "CLOSE"
        assert data["lot_size"] == 0.10
        assert data["ticket"] == 99999
        assert data["stop_loss"] == 0.01
        assert data["take_profit"] == 0.01

    async def test_orphan_invalid_payload(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "ticket": 99999,
                "symbol": "XAUUSD",
                # missing direction, lot_size, open_price, open_time
            }
            response = await ac.post("/api/v1/position/orphan", json=payload)
        assert response.status_code == 422

    async def test_orphan_requires_auth(self, unauth_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "ticket": 99999,
                "symbol": "XAUUSD",
                "direction": "SELL",
                "lot_size": 0.10,
                "open_price": 2030.00,
                "open_time": "2024-01-15T09:00:00Z",
            }
            response = await ac.post("/api/v1/position/orphan", json=payload)
        assert response.status_code == 401
