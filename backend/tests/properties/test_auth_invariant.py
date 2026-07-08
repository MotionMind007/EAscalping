"""Property-based test for authentication invariant.

Validates that all protected endpoints require valid Bearer token authentication.
Endpoints without auth token receive 401, endpoints with valid token are processed.

**Validates: Requirements 1.13**
"""
import os
import pytest
from hypothesis import HealthCheck, Phase, given, settings
from hypothesis import strategies as st
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.dependencies import get_settings

# Set test environment variables before any imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AUTH_TOKEN", "test-token-secret")

# List of all protected endpoints in the backend
PROTECTED_ENDPOINTS = [
    # Market router
    ("/api/v1/market/tick", "POST", {"symbol": "XAUUSD", "ticks": [{"timestamp": "2024-01-15T10:30:00Z", "bid": 2025.5, "ask": 2025.6, "spread": 1}]}),
    ("/api/v1/market/candle", "POST", {"symbol": "XAUUSD", "timeframe": "M1", "timestamp": "2024-01-15T10:30:00Z", "open": 2025.0, "high": 2026.0, "low": 2024.0, "close": 2025.5, "volume": 100}),
    # Health router
    ("/api/v1/health/heartbeat", "POST", {"state": "CONNECT", "account_balance": 10000.0, "account_equity": 10000.0, "latency_ms": 50, "mt5_connected": True, "spread": 1, "timestamp": "2024-01-15T10:30:00Z"}),
    ("/api/v1/health/mt5disconnect", "POST", {"state": "CONNECT", "timestamp": "2024-01-15T10:30:00Z"}),
    ("/api/v1/health/mt5reconnect", "POST", {"state": "CONNECT", "account_balance": 10000.0, "account_equity": 10000.0, "timestamp": "2024-01-15T10:30:00Z"}),
    # State router
    ("/api/v1/state/transition", "POST", {"current_state": "CONNECT", "requested_state": "WAIT_SESSION", "reason": "test", "timestamp": "2024-01-15T10:30:00Z"}),
    ("/api/v1/state/recovery", "POST", {"current_state": "CONNECT", "account_equity": 10000.0, "open_position": None, "timestamp": "2024-01-15T10:30:00Z"}),
    # Trade router
    ("/api/v1/trade/result", "POST", {"success": True, "ticket": 12345, "fill_price": 2025.50, "command_type": "BUY", "timestamp": "2024-01-15T10:30:00Z"}),
    # Position router
    ("/api/v1/position/status", "POST", {"ticket": 12345, "symbol": "XAUUSD", "direction": "BUY", "lot_size": 0.1, "open_price": 2025.5, "current_price": 2026.0, "unrealized_pnl": 5.0, "timestamp": "2024-01-15T10:30:00Z"}),
    ("/api/v1/position/known", "POST", {"symbol": "XAUUSD"}),
    ("/api/v1/position/orphan", "POST", {"ticket": 99999, "symbol": "XAUUSD", "direction": "SELL", "lot_size": 0.1, "open_price": 2030.0, "open_time": "2024-01-15T09:00:00Z"}),
]


def random_invalid_tokens():
    """Generate various invalid/missing token scenarios with ASCII-only characters."""
    # Generate random ASCII string using only alphanumeric and common symbols
    ascii_chars = st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=[])
    ascii_text = st.text(alphabet=ascii_chars, min_size=1, max_size=50)
    
    return st.one_of([
        st.none(),  # Missing header entirely
        st.just(""),  # Empty token
        ascii_text,  # Random ASCII token
        st.uuids().map(str),  # UUID format
    ])


@pytest.mark.property
@pytest.mark.asyncio
class TestAuthInvariant:
    """Property-based tests for authentication invariant."""

    @pytest.mark.parametrize("endpoint, method, payload", PROTECTED_ENDPOINTS)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
        phases=[Phase.generate],
    )
    @given(token=random_invalid_tokens())
    async def test_protected_endpoints_require_auth(
        self,
        endpoint: str,
        method: str,
        payload: dict,
        token: str | None,
    ):
        """
        Property: For any protected endpoint, any request without valid Bearer token
        must receive HTTP 401 response.
        
        This test covers:
        - Missing X-Auth-Token header
        - Empty X-Auth-Token header
        - Invalid/random token values
        - All protected endpoints in the backend
        """
        # Clear cached settings
        get_settings.cache_clear()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {}
            if token is not None:
                headers["X-Auth-Token"] = token
                
            response = await ac.request(method, endpoint, json=payload, headers=headers)
        
        # Verify 401 for invalid/missing tokens
        assert response.status_code == 401, (
            f"Expected 401 for invalid token on {method} {endpoint}, "
            f"got {response.status_code}. Response: {response.text}"
        )

    @pytest.mark.parametrize("endpoint, method, payload", PROTECTED_ENDPOINTS)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
        phases=[Phase.generate],
    )
    @given(token=st.text(min_size=1, max_size=256))
    async def test_protected_endpoints_accept_valid_token(
        self,
        endpoint: str,
        method: str,
        payload: dict,
        token: str,
    ):
        """
        Property: For any protected endpoint with a valid Bearer token,
        the request must be processed (not receive 401).
        
        Note: We use the configured AUTH_TOKEN from settings as the valid token.
        Any other token value results in 401.
        """
        # Clear cached settings
        get_settings.cache_clear()
        
        # Get the actual auth token from settings
        valid_token = get_settings().auth_token
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"X-Auth-Token": valid_token}
            response = await ac.request(method, endpoint, json=payload, headers=headers)
        
        # Verify request is processed (not 401)
        # Status should be 200 for successful processing or 422 for validation errors
        assert response.status_code != 401, (
            f"Expected non-401 status for valid token on {method} {endpoint}, "
            f"got {response.status_code}. Response: {response.text}"
        )

    @pytest.mark.parametrize("endpoint, method, payload", PROTECTED_ENDPOINTS)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
        phases=[Phase.generate],
    )
    @given(token=st.none())
    async def test_missing_auth_token_header(
        self,
        endpoint: str,
        method: str,
        payload: dict,
        token: None,
    ):
        """
        Property: Requests without the X-Auth-Token header must receive 401.
        """
        # Clear cached settings
        get_settings.cache_clear()
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Don't include X-Auth-Token header at all
            response = await ac.request(method, endpoint, json=payload)
        
        assert response.status_code == 401, (
            f"Expected 401 for missing token header on {method} {endpoint}, "
            f"got {response.status_code}. Response: {response.text}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
        phases=[Phase.generate],
    )
    @given(
        endpoint=st.sampled_from(PROTECTED_ENDPOINTS),
        extra_headers=st.dictionaries(
            keys=st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
            values=st.text(min_size=1, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
            max_size=5
        )
    )
    async def test_random_extra_headers_dont_bypass_auth(
        self,
        endpoint: tuple,
        extra_headers: dict,
    ):
        """
        Property: Adding random extra headers does not bypass authentication.
        Requests without valid X-Auth-Token must still receive 401.
        """
        # Clear cached settings
        get_settings.cache_clear()
        
        endpoint_path, method, payload = endpoint
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"X-Auth-Token": ""}  # Invalid token
            headers.update(extra_headers)
            response = await ac.request(method, endpoint_path, json=payload, headers=headers)
        
        assert response.status_code == 401, (
            f"Expected 401 despite extra headers on {method} {endpoint_path}, "
            f"got {response.status_code}. Response: {response.text}"
        )
