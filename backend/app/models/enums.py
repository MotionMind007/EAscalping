"""Enumerations for the Backend Gateway.

Defines typed string enums for EA states, trade directions, command types,
trade status, and risk status. Using str+Enum allows Pydantic to serialize/
deserialize these as plain strings in JSON payloads.
"""
from enum import Enum


class EAState(str, Enum):
    """EA finite state machine states."""

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


class Direction(str, Enum):
    """Trade direction."""

    BUY = "BUY"
    SELL = "SELL"


class CommandType(str, Enum):
    """Trade command types sent to the EA."""

    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"


class TradeStatus(str, Enum):
    """Trade lifecycle status."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class RiskStatus(str, Enum):
    """Risk engine status."""

    CLEAR = "CLEAR"
    RISK_LOCK = "RISK_LOCK"
