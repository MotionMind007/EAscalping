"""
Python mirror implementation of CHealthMonitor heartbeat serialization
(Include/EAGateway/HealthMonitor.mqh).

This module mirrors the heartbeat payload serialization logic for property-based testing.
It validates that heartbeat payloads always include all required fields as per Requirements 5.2.

Feature: ea-gateway
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------
# Enums matching MQL5 Types.mqh
# --------------------------------------------------------------------------

class EAState(Enum):
    BOOT = "BOOT"
    CONNECT = "CONNECT"
    WAIT_SESSION = "WAIT_SESSION"
    CHECK_RISK = "CHECK_RISK"
    SCAN_SIGNAL = "SCAN_SIGNAL"
    AI_CONFIRMATION = "AI_CONFIRMATION"
    OPEN_POSITION = "OPEN_POSITION"
    MANAGE_POSITION = "MANAGE_POSITION"
    POSITION_CLOSED = "POSITION_CLOSED"
    DISCONNECTED = "DISCONNECTED"


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class HealthState:
    """Represents the current health state of the EA for heartbeat serialization."""
    state: EAState = EAState.WAIT_SESSION
    account_balance: float = 0.0
    account_equity: float = 0.0
    latency_ms: int = 0
    mt5_connected: bool = True
    spread: int = 0


# --------------------------------------------------------------------------
# Heartbeat Serializer (mirror of CHealthMonitor::SerializeHeartbeat)
# --------------------------------------------------------------------------

class HeartbeatSerializer:
    """
    Python mirror of CHealthMonitor heartbeat serialization.

    Mirrors the SerializeHeartbeat() method which builds the JSON payload
    sent to POST /api/v1/health/heartbeat every 30 seconds.

    Required fields per Requirements 5.2:
      - state: EA state (string)
      - account_balance: account balance (number)
      - account_equity: account equity (number)
      - latency_ms: connection latency in ms (integer)
      - mt5_connected: MT5 server connection status (boolean)
      - spread: current spread in points (integer)
    """

    # Required fields that must always be present in the heartbeat payload
    REQUIRED_FIELDS = {
        "state",
        "account_balance",
        "account_equity",
        "latency_ms",
        "mt5_connected",
        "spread",
    }

    def serialize_heartbeat(self, health_state: HealthState) -> str:
        """
        Serialize a heartbeat payload to JSON string.

        Mirrors CHealthMonitor::SerializeHeartbeat() from HealthMonitor.mqh.
        Always includes all required fields regardless of input values.

        Args:
            health_state: Current health state data

        Returns:
            JSON string with all required heartbeat fields
        """
        payload = {
            "state": health_state.state.value,
            "account_balance": round(health_state.account_balance, 2),
            "account_equity": round(health_state.account_equity, 2),
            "latency_ms": health_state.latency_ms,
            "mt5_connected": health_state.mt5_connected,
            "spread": health_state.spread,
        }
        return json.dumps(payload)

    def validate_payload_completeness(self, json_payload: str) -> bool:
        """
        Validate that a heartbeat payload contains all required fields.

        Args:
            json_payload: The serialized JSON heartbeat payload

        Returns:
            True if all required fields are present, False otherwise
        """
        try:
            data = json.loads(json_payload)
        except (json.JSONDecodeError, ValueError):
            return False

        if not isinstance(data, dict):
            return False

        return self.REQUIRED_FIELDS.issubset(data.keys())

    def validate_field_types(self, json_payload: str) -> bool:
        """
        Validate that heartbeat payload fields have correct types.

        - state: string
        - account_balance: number
        - account_equity: number
        - latency_ms: integer
        - mt5_connected: boolean
        - spread: integer

        Args:
            json_payload: The serialized JSON heartbeat payload

        Returns:
            True if all field types are correct, False otherwise
        """
        try:
            data = json.loads(json_payload)
        except (json.JSONDecodeError, ValueError):
            return False

        if not isinstance(data, dict):
            return False

        # Check each field's type
        if not isinstance(data.get("state"), str):
            return False
        if not isinstance(data.get("account_balance"), (int, float)):
            return False
        if not isinstance(data.get("account_equity"), (int, float)):
            return False
        if not isinstance(data.get("latency_ms"), int):
            return False
        if not isinstance(data.get("mt5_connected"), bool):
            return False
        if not isinstance(data.get("spread"), int):
            return False

        return True
