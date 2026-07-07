"""
Python mirror implementation of CCommandDispatcher (Include/EAGateway/CommandDispatcher.mqh).

This module provides the same logic as the MQL5 implementation for property-based testing.
It mirrors:
  - Trade command JSON parsing
  - State transition response parsing
  - Session-based command filtering (BUY/SELL rejected outside session, CLOSE always allowed)
  - Command dispatch routing

Feature: ea-gateway
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple
from datetime import datetime, timezone


# --------------------------------------------------------------------------
# Enums matching MQL5 Types.mqh
# --------------------------------------------------------------------------

class TradeCommandType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"


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
class TradeCommand:
    type: TradeCommandType = TradeCommandType.BUY
    lot_size: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    ticket: int = 0


@dataclass
class TradeResult:
    success: bool = False
    ticket: int = 0
    fill_price: float = 0.0
    slippage_points: int = 0
    error_code: int = 0
    error_message: str = ""


@dataclass
class StateResponse:
    approved: bool = False
    new_state: str = ""
    command: Optional[TradeCommand] = None
    has_command: bool = False


@dataclass
class DispatchResult:
    dispatched: bool = False
    rejected_session: bool = False
    rejection_report: Optional[dict] = None
    trade_result: Optional[TradeResult] = None


# --------------------------------------------------------------------------
# Session Manager (mirror of SessionManager.mqh)
# --------------------------------------------------------------------------

class SessionManager:
    """Mirrors CSessionManager session window logic."""

    def __init__(self):
        self.london_start_hour = 8
        self.london_end_hour = 16
        self.ny_start_hour = 13
        self.ny_end_hour = 21

    def is_in_session(self, utc_hour: int) -> bool:
        """Combined session window: [8, 21) UTC."""
        return self.london_start_hour <= utc_hour < self.ny_end_hour

    def can_open_trade(self, utc_hour: int) -> bool:
        """BUY/SELL allowed only in session."""
        return self.is_in_session(utc_hour)

    def can_close_trade(self) -> bool:
        """CLOSE always allowed regardless of session."""
        return True


# --------------------------------------------------------------------------
# Command Dispatcher (mirror of CommandDispatcher.mqh)
# --------------------------------------------------------------------------

class CommandDispatcher:
    """
    Python mirror of CCommandDispatcher.

    Parses trade commands from JSON, filters through session window,
    and dispatches to trade execution.
    """

    SESSION_ERROR_CODE = -2

    def __init__(self, session_manager: Optional[SessionManager] = None):
        self.session_manager = session_manager or SessionManager()

    def parse_trade_command(self, json_body: str) -> Tuple[bool, TradeCommand]:
        """
        Parse Trade_Command JSON from backend response.

        Returns (success, TradeCommand).
        """
        cmd = TradeCommand()

        if not json_body or not json_body.strip():
            return False, cmd

        try:
            data = json.loads(json_body)
        except (json.JSONDecodeError, ValueError):
            return False, cmd

        if not isinstance(data, dict):
            return False, cmd

        # Extract "type" field (required)
        type_str = data.get("type", "")
        if not type_str:
            return False, cmd

        if type_str == "BUY":
            cmd.type = TradeCommandType.BUY
        elif type_str == "SELL":
            cmd.type = TradeCommandType.SELL
        elif type_str == "CLOSE":
            cmd.type = TradeCommandType.CLOSE
        else:
            return False, cmd

        # Extract numeric fields
        cmd.lot_size = float(data.get("lot_size", 0.0) or 0.0)
        cmd.stop_loss = float(data.get("stop_loss", 0.0) or 0.0)
        cmd.take_profit = float(data.get("take_profit", 0.0) or 0.0)
        cmd.ticket = int(data.get("ticket", 0) or 0)

        # Validate required fields per command type
        if cmd.type in (TradeCommandType.BUY, TradeCommandType.SELL):
            if cmd.lot_size <= 0.0:
                return False, cmd
        elif cmd.type == TradeCommandType.CLOSE:
            if cmd.ticket <= 0:
                return False, cmd

        return True, cmd

    def parse_state_response(self, json_body: str) -> Tuple[bool, StateResponse]:
        """
        Parse state transition response from backend.

        Expected format:
        {
          "approved": true,
          "new_state": "CHECK_RISK",
          "command": null OR { "type": "BUY", ... }
        }

        Returns (success, StateResponse).
        """
        resp = StateResponse()

        if not json_body or not json_body.strip():
            return False, resp

        try:
            data = json.loads(json_body)
        except (json.JSONDecodeError, ValueError):
            return False, resp

        if not isinstance(data, dict):
            return False, resp

        resp.approved = bool(data.get("approved", False))
        resp.new_state = str(data.get("new_state", "") or "")

        # Parse embedded command
        command_data = data.get("command")
        if command_data is not None and isinstance(command_data, dict):
            cmd_json = json.dumps(command_data)
            success, cmd = self.parse_trade_command(cmd_json)
            if success:
                resp.command = cmd
                resp.has_command = True

        return True, resp

    def dispatch_command(self, cmd: TradeCommand, utc_hour: int) -> DispatchResult:
        """
        Route command through session filter.

        Logic:
        - BUY/SELL: reject if outside session window
        - CLOSE: always allow
        - Returns dispatch result with rejection details if filtered

        Args:
            cmd: The trade command to dispatch
            utc_hour: Current UTC hour (0-23) for session check
        """
        result = DispatchResult()

        # Session filter for BUY/SELL
        if cmd.type in (TradeCommandType.BUY, TradeCommandType.SELL):
            if not self.session_manager.is_in_session(utc_hour):
                result.dispatched = False
                result.rejected_session = True
                result.rejection_report = self._build_session_rejection(cmd)
                return result

        # Command passes filter - would be dispatched to TradeExecutor
        result.dispatched = True
        result.rejected_session = False
        return result

    def _build_session_rejection(self, cmd: TradeCommand) -> dict:
        """Build JSON rejection report for session-filtered commands."""
        return {
            "success": False,
            "error_code": self.SESSION_ERROR_CODE,
            "error_message": "Trade rejected: outside session window",
            "command_type": cmd.type.value,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
