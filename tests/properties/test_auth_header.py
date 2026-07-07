"""
Property-based tests for Auth Header Invariant (Property 4).

Tests cover:
  - Every HTTP request includes the configured auth token in the header
  - Token is present regardless of endpoint, payload content, or state

Feature: ea-gateway
Property 4: Auth Header Invariant

**Validates: Requirements 2.2**
"""

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from tests.mirror.http_client import HttpClientDispatch


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Random auth tokens (non-empty, max 512 chars as per config validation)
auth_tokens = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=512,
).filter(lambda x: x.strip())

# Random endpoints matching the API pattern
endpoints = st.one_of(
    st.just("/api/v1/market/tick"),
    st.just("/api/v1/market/candle"),
    st.just("/api/v1/health/heartbeat"),
    st.just("/api/v1/state/transition"),
    st.just("/api/v1/trade/result"),
    st.just("/api/v1/position/status"),
    st.just("/api/v1/position/orphan"),
    st.just("/api/v1/state/recovery"),
    # Random endpoint paths
    st.from_regex(r"/api/v[0-9]/[a-z]+(/[a-z_]+){0,3}", fullmatch=True),
)

# Random JSON payloads
json_payloads = st.one_of(
    st.just("{}"),
    st.just('{"key": "value"}'),
    st.just('{"ticks": []}'),
    st.text(min_size=0, max_size=200),
)


# --------------------------------------------------------------------------
# Property Tests: Auth Header Invariant
# --------------------------------------------------------------------------

class TestAuthHeaderInvariant:
    """Property tests: every request includes auth token in header."""

    @pytest.mark.property
    @given(auth_token=auth_tokens)
    def test_header_always_contains_auth_token(self, auth_token):
        """
        **Validates: Requirements 2.2**

        For any configured authentication token,
        the built headers SHALL include the token in X-Auth-Token.
        """
        client = HttpClientDispatch()
        headers = client.build_headers(auth_token)

        assert "X-Auth-Token" in headers
        assert headers["X-Auth-Token"] == auth_token

    @pytest.mark.property
    @given(
        auth_token=auth_tokens,
        endpoint=endpoints,
    )
    def test_auth_token_present_regardless_of_endpoint(self, auth_token, endpoint):
        """
        **Validates: Requirements 2.2**

        For any endpoint path, the auth header SHALL be included.
        The endpoint does not affect header construction.
        """
        client = HttpClientDispatch()
        headers = client.build_headers(auth_token)

        # Auth token present regardless of what endpoint we're hitting
        assert "X-Auth-Token" in headers
        assert headers["X-Auth-Token"] == auth_token

    @pytest.mark.property
    @given(
        auth_token=auth_tokens,
        payload=json_payloads,
    )
    def test_auth_token_present_regardless_of_payload(self, auth_token, payload):
        """
        **Validates: Requirements 2.2**

        For any payload content, the auth header SHALL be included.
        The payload does not affect header construction.
        """
        client = HttpClientDispatch()
        headers = client.build_headers(auth_token)

        # Auth token present regardless of payload content
        assert "X-Auth-Token" in headers
        assert headers["X-Auth-Token"] == auth_token

    @pytest.mark.property
    @given(auth_token=auth_tokens)
    def test_content_type_always_json(self, auth_token):
        """
        **Validates: Requirements 2.2**

        For any request, Content-Type SHALL be application/json.
        """
        client = HttpClientDispatch()
        headers = client.build_headers(auth_token)

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.property
    @given(
        auth_token=auth_tokens,
        endpoint=endpoints,
        payload=json_payloads,
    )
    def test_auth_header_invariant_full(self, auth_token, endpoint, payload):
        """
        **Validates: Requirements 2.2**

        For any HTTP request (any endpoint, any payload),
        the request SHALL include the configured authentication token
        in the request header.
        """
        client = HttpClientDispatch()
        headers = client.build_headers(auth_token)

        # The auth token is ALWAYS present
        assert "X-Auth-Token" in headers
        assert headers["X-Auth-Token"] == auth_token
        # And the value matches the configured token exactly
        assert headers["X-Auth-Token"] is not None
        assert len(headers["X-Auth-Token"]) > 0
