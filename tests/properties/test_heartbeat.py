"""
Property-based tests for Heartbeat Payload Completeness (Property 11).

**Validates: Requirements 5.2**

Property: *For any* heartbeat sent by the EA, the serialized payload SHALL include
all required fields: EA state (string), account balance (number), account equity (number),
connection latency in ms (integer), MT5 server connection status (boolean), and current
spread in points (integer).

Feature: ea-gateway, Property 11: Heartbeat Payload Completeness
"""

import json
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.mirror.health_monitor import (
    HeartbeatSerializer,
    HealthState,
    EAState,
)


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

ea_states = st.sampled_from(list(EAState))

# Account balances: realistic trading ranges including edge cases
account_balances = st.floats(
    min_value=0.0, max_value=1_000_000.0,
    allow_nan=False, allow_infinity=False,
)

# Account equities: can be above or below balance due to unrealized P/L
account_equities = st.floats(
    min_value=-100_000.0, max_value=1_000_000.0,
    allow_nan=False, allow_infinity=False,
)

# Latency: realistic range in milliseconds (0 = not measured yet, up to 30s timeout)
latencies = st.integers(min_value=0, max_value=30_000)

# MT5 connection status
mt5_connected = st.booleans()

# Spread in points (XAUUSD typically 20-100 points, but can spike)
spreads = st.integers(min_value=0, max_value=10_000)

# Composite strategy for full health states
health_states = st.builds(
    HealthState,
    state=ea_states,
    account_balance=account_balances,
    account_equity=account_equities,
    latency_ms=latencies,
    mt5_connected=mt5_connected,
    spread=spreads,
)


# --------------------------------------------------------------------------
# Property Tests
# --------------------------------------------------------------------------

class TestHeartbeatPayloadCompleteness:
    """Property 11: Heartbeat Payload Completeness."""

    @pytest.mark.property
    @given(health_state=health_states)
    def test_payload_always_includes_all_required_fields(self, health_state):
        """
        **Validates: Requirements 5.2**

        For any health state (random balance, equity, latency, state, spread,
        mt5 connection status), the serialized heartbeat payload SHALL always
        include ALL required fields: state, account_balance, account_equity,
        latency_ms, mt5_connected, spread.
        """
        serializer = HeartbeatSerializer()
        payload_json = serializer.serialize_heartbeat(health_state)

        assert serializer.validate_payload_completeness(payload_json), (
            f"Heartbeat payload missing required fields. "
            f"Got: {json.loads(payload_json).keys()}, "
            f"Required: {serializer.REQUIRED_FIELDS}"
        )

    @pytest.mark.property
    @given(health_state=health_states)
    def test_payload_fields_have_correct_types(self, health_state):
        """
        **Validates: Requirements 5.2**

        For any health state, the heartbeat payload fields SHALL have their
        correct types: state (string), account_balance (number),
        account_equity (number), latency_ms (integer), mt5_connected (boolean),
        spread (integer).
        """
        serializer = HeartbeatSerializer()
        payload_json = serializer.serialize_heartbeat(health_state)

        assert serializer.validate_field_types(payload_json), (
            f"Heartbeat payload has incorrect field types. Payload: {payload_json}"
        )

    @pytest.mark.property
    @given(health_state=health_states)
    def test_state_field_is_valid_ea_state(self, health_state):
        """
        **Validates: Requirements 5.2**

        For any heartbeat, the state field SHALL be a valid EA state string
        (one of the defined EAState enum values).
        """
        serializer = HeartbeatSerializer()
        payload_json = serializer.serialize_heartbeat(health_state)
        data = json.loads(payload_json)

        valid_states = {s.value for s in EAState}
        assert data["state"] in valid_states, (
            f"Invalid state '{data['state']}' in heartbeat. "
            f"Valid states: {valid_states}"
        )

    @pytest.mark.property
    @given(health_state=health_states)
    def test_payload_is_valid_json(self, health_state):
        """
        **Validates: Requirements 5.2**

        For any heartbeat, the serialized payload SHALL be valid JSON
        that can be parsed without errors.
        """
        serializer = HeartbeatSerializer()
        payload_json = serializer.serialize_heartbeat(health_state)

        # Should not raise
        data = json.loads(payload_json)
        assert isinstance(data, dict)

    @pytest.mark.property
    @given(health_state=health_states)
    def test_numeric_values_preserved(self, health_state):
        """
        **Validates: Requirements 5.2**

        For any heartbeat, numeric values (balance, equity, latency, spread)
        SHALL be preserved in the serialized payload with appropriate precision.
        """
        serializer = HeartbeatSerializer()
        payload_json = serializer.serialize_heartbeat(health_state)
        data = json.loads(payload_json)

        # Balance and equity rounded to 2 decimal places
        assert abs(data["account_balance"] - round(health_state.account_balance, 2)) < 1e-9
        assert abs(data["account_equity"] - round(health_state.account_equity, 2)) < 1e-9

        # Integer fields preserved exactly
        assert data["latency_ms"] == health_state.latency_ms
        assert data["spread"] == health_state.spread
        assert data["mt5_connected"] == health_state.mt5_connected
