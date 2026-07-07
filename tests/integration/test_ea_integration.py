"""
Integration tests for the EA Gateway mock backend.

Tests verify that each endpoint correctly records requests and
returns appropriate responses following the spec payload formats.

Feature: ea-gateway
Validates: Requirements 2.1, 2.3, 2.4, 2.5, 2.6, 2.7
"""

import pytest
import pytest_asyncio
import httpx

from tests.integration.mock_backend import MockBackend, create_mock_backend


@pytest.fixture
def backend() -> MockBackend:
    """Create a fresh mock backend for each test."""
    return create_mock_backend()


@pytest_asyncio.fixture
async def client(backend: MockBackend):
    """Create an httpx AsyncClient connected to the mock backend."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=backend.app),
        base_url="http://test",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tick Forwarding
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tick_forwarding_payload_format(backend: MockBackend, client: httpx.AsyncClient):
    """Verify tick data is received with correct spec format."""
    payload = {
        "symbol": "XAUUSD",
        "ticks": [
            {
                "timestamp": "2024-01-15T10:30:00.123Z",
                "bid": 2035.50,
                "ask": 2035.80,
                "spread": 30,
            }
        ],
    }

    response = await client.post(
        "/api/v1/market/tick",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "received"}

    recorded = backend.get_requests_for("/api/v1/market/tick")
    assert len(recorded) == 1
    assert recorded[0].body["symbol"] == "XAUUSD"
    assert len(recorded[0].body["ticks"]) == 1
    assert recorded[0].body["ticks"][0]["bid"] == 2035.50
    assert recorded[0].body["ticks"][0]["ask"] == 2035.80
    assert recorded[0].body["ticks"][0]["spread"] == 30
    assert "timestamp" in recorded[0].body["ticks"][0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tick_forwarding_batch(backend: MockBackend, client: httpx.AsyncClient):
    """Verify batched tick data (multiple ticks in one POST)."""
    payload = {
        "symbol": "XAUUSD",
        "ticks": [
            {"timestamp": "2024-01-15T10:30:00.100Z", "bid": 2035.50, "ask": 2035.80, "spread": 30},
            {"timestamp": "2024-01-15T10:30:00.110Z", "bid": 2035.51, "ask": 2035.81, "spread": 30},
            {"timestamp": "2024-01-15T10:30:00.120Z", "bid": 2035.52, "ask": 2035.82, "spread": 30},
        ],
    }

    response = await client.post("/api/v1/market/tick", json=payload)
    assert response.status_code == 200

    recorded = backend.get_requests_for("/api/v1/market/tick")
    assert len(recorded) == 1
    assert len(recorded[0].body["ticks"]) == 3


# ---------------------------------------------------------------------------
# Candle Forwarding
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_candle_forwarding_payload_format(backend: MockBackend, client: httpx.AsyncClient):
    """Verify candle data is received with correct spec format."""
    payload = {
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "timestamp": "2024-01-15T10:30:00.000Z",
        "open": 2035.20,
        "high": 2035.90,
        "low": 2035.10,
        "close": 2035.50,
        "volume": 1234,
    }

    response = await client.post(
        "/api/v1/market/candle",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "received"}

    recorded = backend.get_requests_for("/api/v1/market/candle")
    assert len(recorded) == 1
    body = recorded[0].body
    assert body["symbol"] == "XAUUSD"
    assert body["timeframe"] == "M1"
    assert body["open"] == 2035.20
    assert body["high"] == 2035.90
    assert body["low"] == 2035.10
    assert body["close"] == 2035.50
    assert body["volume"] == 1234
    assert "timestamp" in body


# ---------------------------------------------------------------------------
# Heartbeat Payload Completeness
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_heartbeat_payload_completeness(backend: MockBackend, client: httpx.AsyncClient):
    """Verify heartbeat contains all required fields per spec."""
    payload = {
        "state": "WAIT_SESSION",
        "account_balance": 10000.00,
        "account_equity": 10050.00,
        "latency_ms": 45,
        "mt5_connected": True,
        "spread": 30,
        "timestamp": "2024-01-15T10:30:00.000Z",
    }

    response = await client.post("/api/v1/health/heartbeat", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    recorded = backend.get_requests_for("/api/v1/health/heartbeat")
    assert len(recorded) == 1
    body = recorded[0].body

    # All required fields must be present
    assert "state" in body
    assert "account_balance" in body
    assert "account_equity" in body
    assert "latency_ms" in body
    assert "mt5_connected" in body
    assert "spread" in body
    assert "timestamp" in body

    # Type checks
    assert isinstance(body["state"], str)
    assert isinstance(body["account_balance"], (int, float))
    assert isinstance(body["account_equity"], (int, float))
    assert isinstance(body["latency_ms"], int)
    assert isinstance(body["mt5_connected"], bool)
    assert isinstance(body["spread"], int)


# ---------------------------------------------------------------------------
# State Transition Request/Response Flow
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_state_transition_approved(backend: MockBackend, client: httpx.AsyncClient):
    """Verify state transition request/response flow (approved)."""
    backend.configure_endpoint(
        "/api/v1/state/transition",
        body={"approved": True, "new_state": "CHECK_RISK", "command": None},
    )

    payload = {
        "current_state": "WAIT_SESSION",
        "requested_state": "CHECK_RISK",
        "reason": "session_active",
        "timestamp": "2024-01-15T10:30:00.000Z",
    }

    response = await client.post("/api/v1/state/transition", json=payload)

    assert response.status_code == 200
    resp_body = response.json()
    assert resp_body["approved"] is True
    assert resp_body["new_state"] == "CHECK_RISK"
    assert resp_body["command"] is None

    recorded = backend.get_requests_for("/api/v1/state/transition")
    assert len(recorded) == 1
    assert recorded[0].body["current_state"] == "WAIT_SESSION"
    assert recorded[0].body["requested_state"] == "CHECK_RISK"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_state_transition_rejected(backend: MockBackend, client: httpx.AsyncClient):
    """Verify state transition rejection response."""
    backend.configure_endpoint(
        "/api/v1/state/transition",
        body={"approved": False, "new_state": "WAIT_SESSION", "command": None},
    )

    payload = {
        "current_state": "WAIT_SESSION",
        "requested_state": "CHECK_RISK",
        "reason": "session_active",
        "timestamp": "2024-01-15T10:30:00.000Z",
    }

    response = await client.post("/api/v1/state/transition", json=payload)

    assert response.status_code == 200
    resp_body = response.json()
    assert resp_body["approved"] is False
    assert resp_body["new_state"] == "WAIT_SESSION"


# ---------------------------------------------------------------------------
# Trade Result Reporting
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trade_result_success_reporting(backend: MockBackend, client: httpx.AsyncClient):
    """Verify successful trade result payload format."""
    payload = {
        "success": True,
        "ticket": 123456789,
        "fill_price": 2035.55,
        "slippage_points": 5,
        "command_type": "BUY",
        "timestamp": "2024-01-15T10:30:00.500Z",
    }

    response = await client.post("/api/v1/trade/result", json=payload)

    assert response.status_code == 200
    recorded = backend.get_requests_for("/api/v1/trade/result")
    assert len(recorded) == 1
    body = recorded[0].body
    assert body["success"] is True
    assert body["ticket"] == 123456789
    assert body["fill_price"] == 2035.55
    assert body["slippage_points"] == 5
    assert body["command_type"] == "BUY"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trade_result_failure_reporting(backend: MockBackend, client: httpx.AsyncClient):
    """Verify failed trade result (error) payload format."""
    payload = {
        "success": False,
        "error_code": 10006,
        "error_message": "Requote",
        "command_type": "BUY",
        "timestamp": "2024-01-15T10:30:00.500Z",
    }

    response = await client.post("/api/v1/trade/result", json=payload)

    assert response.status_code == 200
    recorded = backend.get_requests_for("/api/v1/trade/result")
    assert len(recorded) == 1
    body = recorded[0].body
    assert body["success"] is False
    assert body["error_code"] == 10006
    assert body["error_message"] == "Requote"


# ---------------------------------------------------------------------------
# Session Rejection Reporting (Outside Session Trade Commands)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_rejection_reporting(backend: MockBackend, client: httpx.AsyncClient):
    """
    Verify the backend receives trade rejection due to session enforcement.
    The EA reports the rejection via trade/result endpoint.
    """
    payload = {
        "success": False,
        "error_code": 0,
        "error_message": "Trade rejected: outside session window",
        "command_type": "BUY",
        "timestamp": "2024-01-15T22:00:00.000Z",
    }

    response = await client.post("/api/v1/trade/result", json=payload)

    assert response.status_code == 200
    recorded = backend.get_requests_for("/api/v1/trade/result")
    assert len(recorded) == 1
    body = recorded[0].body
    assert body["success"] is False
    assert "outside session" in body["error_message"].lower()


# ---------------------------------------------------------------------------
# Recovery Flow
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_recovery_flow(backend: MockBackend, client: httpx.AsyncClient):
    """Verify recovery request/response flow after reconnection."""
    backend.configure_endpoint(
        "/api/v1/state/recovery",
        body={"confirmed_state": "MANAGE_POSITION", "command": None},
    )

    payload = {
        "current_state": "MANAGE_POSITION",
        "open_position": {
            "ticket": 123456789,
            "direction": "BUY",
            "lot_size": 0.10,
            "open_price": 2035.55,
        },
        "account_equity": 10050.00,
        "timestamp": "2024-01-15T10:30:00.000Z",
    }

    response = await client.post("/api/v1/state/recovery", json=payload)

    assert response.status_code == 200
    resp_body = response.json()
    assert resp_body["confirmed_state"] == "MANAGE_POSITION"

    recorded = backend.get_requests_for("/api/v1/state/recovery")
    assert len(recorded) == 1
    body = recorded[0].body
    assert body["current_state"] == "MANAGE_POSITION"
    assert body["open_position"]["ticket"] == 123456789
    assert body["open_position"]["direction"] == "BUY"
    assert body["account_equity"] == 10050.00


# ---------------------------------------------------------------------------
# Configurable Response Behaviors
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_4xx_error_response(backend: MockBackend, client: httpx.AsyncClient):
    """Verify the backend can return 4xx errors for testing error handling."""
    backend.configure_endpoint(
        "/api/v1/market/tick",
        status_code=400,
        body={"error": "Bad request: missing symbol field"},
    )

    response = await client.post("/api/v1/market/tick", json={"ticks": []})

    assert response.status_code == 400
    assert response.json()["error"] == "Bad request: missing symbol field"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_5xx_error_response(backend: MockBackend, client: httpx.AsyncClient):
    """Verify the backend can return 5xx errors for testing retry logic."""
    backend.configure_endpoint(
        "/api/v1/health/heartbeat",
        status_code=500,
        body={"error": "Internal server error"},
    )

    response = await client.post("/api/v1/health/heartbeat", json={"state": "CONNECT"})

    assert response.status_code == 500
    assert response.json()["error"] == "Internal server error"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_json_response(backend: MockBackend, client: httpx.AsyncClient):
    """Verify the backend can return invalid JSON for testing parser resilience."""
    backend.configure_endpoint(
        "/api/v1/state/transition",
        return_invalid_json=True,
    )

    payload = {
        "current_state": "WAIT_SESSION",
        "requested_state": "CHECK_RISK",
        "reason": "session_active",
        "timestamp": "2024-01-15T10:30:00.000Z",
    }

    response = await client.post("/api/v1/state/transition", json=payload)

    # Should get the raw invalid content
    assert response.text == "this is not valid json {{{"

    # Request still gets recorded
    recorded = backend.get_requests_for("/api/v1/state/transition")
    assert len(recorded) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reset_clears_state(backend: MockBackend, client: httpx.AsyncClient):
    """Verify reset clears all recorded requests and configurations."""
    # Make some requests
    await client.post("/api/v1/market/tick", json={"symbol": "XAUUSD", "ticks": []})
    await client.post("/api/v1/market/candle", json={"symbol": "XAUUSD", "timeframe": "M1"})

    assert len(backend.requests) == 2

    # Configure endpoint
    backend.configure_endpoint("/api/v1/market/tick", status_code=503)

    # Reset
    backend.reset()

    assert len(backend.requests) == 0
    assert len(backend.endpoint_configs) == 0

    # Default behavior restored
    response = await client.post("/api/v1/market/tick", json={"symbol": "XAUUSD", "ticks": []})
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_header_recorded(backend: MockBackend, client: httpx.AsyncClient):
    """Verify authorization headers are recorded for assertion."""
    await client.post(
        "/api/v1/health/heartbeat",
        json={"state": "WAIT_SESSION"},
        headers={"Authorization": "Bearer my-secret-token"},
    )

    recorded = backend.get_requests_for("/api/v1/health/heartbeat")
    assert len(recorded) == 1
    assert "authorization" in recorded[0].headers
    assert recorded[0].headers["authorization"] == "Bearer my-secret-token"
