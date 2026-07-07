"""Unit tests for Wave 2 routers: market, health, and state.

Uses FastAPI TestClient with mocked Redis dependency to test endpoint
validation, auth, and response structure without requiring real services.
"""
import json
import time
from unittest.mock import AsyncMock, patch

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
    redis.rpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.hset = AsyncMock()
    redis.expire = AsyncMock()
    redis.delete = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.hgetall = AsyncMock(return_value={})
    redis.ping = AsyncMock()
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
    # Clear the lru_cache so settings picks up env vars
    from app.dependencies import get_settings
    get_settings.cache_clear()

    mock_redis = AsyncMock()
    app.dependency_overrides[get_redis] = lambda: mock_redis
    # Do NOT override verify_auth_token — auth is enforced
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()


# ─── Market Router Tests ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestMarketRouter:
    """Tests for POST /api/v1/market/tick and /api/v1/market/candle."""

    async def test_tick_valid_payload(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "symbol": "XAUUSD",
                "ticks": [
                    {
                        "timestamp": "2024-01-15T10:30:00Z",
                        "bid": 2025.50,
                        "ask": 2025.90,
                        "spread": 40,
                    }
                ],
            }
            response = await ac.post("/api/v1/market/tick", json=payload)
        assert response.status_code == 200
        assert response.json() == {}
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "market:tick:XAUUSD"

    async def test_tick_invalid_payload_missing_symbol(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {"ticks": [{"timestamp": "2024-01-15T10:30:00Z", "bid": 2025.50, "ask": 2025.90, "spread": 40}]}
            response = await ac.post("/api/v1/market/tick", json=payload)
        assert response.status_code == 422

    async def test_tick_invalid_payload_empty_ticks(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {"symbol": "XAUUSD", "ticks": []}
            response = await ac.post("/api/v1/market/tick", json=payload)
        assert response.status_code == 422

    async def test_candle_valid_payload(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "symbol": "XAUUSD",
                "timeframe": "M1",
                "timestamp": "2024-01-15T10:30:00Z",
                "open": 2025.50,
                "high": 2026.00,
                "low": 2025.00,
                "close": 2025.80,
                "volume": 150,
            }
            response = await ac.post("/api/v1/market/candle", json=payload)
        assert response.status_code == 200
        assert response.json() == {}
        mock_redis.rpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()
        # Verify key structure
        call_args = mock_redis.rpush.call_args
        assert call_args[0][0] == "market:candles:XAUUSD:M1"

    async def test_candle_invalid_payload_negative_volume(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "symbol": "XAUUSD",
                "timeframe": "M1",
                "timestamp": "2024-01-15T10:30:00Z",
                "open": 2025.50,
                "high": 2026.00,
                "low": 2025.00,
                "close": 2025.80,
                "volume": -1,
            }
            response = await ac.post("/api/v1/market/candle", json=payload)
        assert response.status_code == 422


# ─── Health Router Tests ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestHealthRouter:
    """Tests for health endpoints."""

    async def test_heartbeat_valid_payload(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "state": "WAIT_SESSION",
                "account_balance": 10000.0,
                "account_equity": 10050.0,
                "latency_ms": 15,
                "mt5_connected": True,
                "spread": 25,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/health/heartbeat", json=payload)
        assert response.status_code == 200
        assert response.json() == {}
        mock_redis.hset.assert_called_once()

    async def test_heartbeat_invalid_state(self, client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "state": "INVALID_STATE",
                "account_balance": 10000.0,
                "account_equity": 10050.0,
                "latency_ms": 15,
                "mt5_connected": True,
                "spread": 25,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/health/heartbeat", json=payload)
        assert response.status_code == 422

    async def test_mt5disconnect_valid(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "event": "mt5_disconnect",
                "state": "WAIT_SESSION",
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/health/mt5disconnect", json=payload)
        assert response.status_code == 200
        mock_redis.set.assert_called_with("signals:paused", "1")

    async def test_mt5reconnect_valid(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "event": "mt5_reconnect",
                "state": "WAIT_SESSION",
                "account_balance": 10000.0,
                "account_equity": 10050.0,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/health/mt5reconnect", json=payload)
        assert response.status_code == 200
        mock_redis.delete.assert_called_with("signals:paused")

    async def test_health_endpoint_no_auth_required(self, client, mock_redis):
        """GET /health should work without auth."""
        mock_redis.hgetall.return_value = {
            "state": "WAIT_SESSION",
            "last_seen": str(time.time()),
            "mt5_connected": "True",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "ea_connected" in data
        assert "redis_connected" in data

    async def test_health_endpoint_ea_disconnected(self, client, mock_redis):
        """GET /health should report ea_connected=false if heartbeat > 90s old."""
        mock_redis.hgetall.return_value = {
            "state": "WAIT_SESSION",
            "last_seen": str(time.time() - 100),  # 100s ago
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ea_connected"] is False
        assert data["status"] == "degraded"


# ─── State Router Tests ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestStateRouter:
    """Tests for state transition and recovery endpoints."""

    async def test_transition_valid(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "current_state": "WAIT_SESSION",
                "requested_state": "CHECK_RISK",
                "reason": "session_active",
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/state/transition", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["approved"] is True
        assert data["new_state"] == "CHECK_RISK"
        mock_redis.set.assert_called_with("ea:state", "CHECK_RISK", ex=120)

    async def test_transition_invalid_pair(self, client, mock_redis):
        """Invalid FSM transition should be rejected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "current_state": "WAIT_SESSION",
                "requested_state": "OPEN_POSITION",
                "reason": "skip_ahead",
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/state/transition", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["approved"] is False
        assert data["new_state"] == "WAIT_SESSION"
        assert "Invalid transition" in data["reason"]

    async def test_transition_invalid_state_value(self, client):
        """Invalid state enum value should return 422."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "current_state": "NONEXISTENT",
                "requested_state": "CHECK_RISK",
                "reason": "test",
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/state/transition", json=payload)
        assert response.status_code == 422

    async def test_recovery_valid(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "current_state": "MANAGE_POSITION",
                "open_position": {"ticket": 12345, "direction": "BUY"},
                "account_equity": 10050.0,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/state/recovery", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["confirmed_state"] == "MANAGE_POSITION"
        assert data["pending_commands"] == []
        mock_redis.set.assert_called_with("ea:state", "MANAGE_POSITION", ex=120)

    async def test_recovery_no_open_position(self, client, mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "current_state": "WAIT_SESSION",
                "open_position": None,
                "account_equity": 10000.0,
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/state/recovery", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["confirmed_state"] == "WAIT_SESSION"


# ─── Auth Tests ───────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAuth:
    """Verify auth is enforced on protected endpoints."""

    async def test_tick_requires_auth(self, unauth_client):
        """POST /market/tick without token should return 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "symbol": "XAUUSD",
                "ticks": [{"timestamp": "2024-01-15T10:30:00Z", "bid": 2025.50, "ask": 2025.90, "spread": 40}],
            }
            response = await ac.post("/api/v1/market/tick", json=payload)
        assert response.status_code == 401

    async def test_transition_requires_auth(self, unauth_client):
        """POST /state/transition without token should return 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "current_state": "WAIT_SESSION",
                "requested_state": "CHECK_RISK",
                "reason": "test",
                "timestamp": "2024-01-15T10:30:00Z",
            }
            response = await ac.post("/api/v1/state/transition", json=payload)
        assert response.status_code == 401
