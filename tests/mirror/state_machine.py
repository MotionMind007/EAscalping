"""
Python mirror implementation of CStateMachine (Include/EAGateway/StateMachine.mqh).

This module provides the same FSM transition logic as the MQL5 implementation
for property-based testing. It mirrors:
  - The 10-state enum (EAState)
  - The transition table (valid from→to pairs)
  - Transition validation (IsValidTransition)
  - State transition execution (TransitionTo)

Feature: ea-gateway
"""

from enum import Enum
from typing import Set, Tuple


# --------------------------------------------------------------------------
# EAState enum matching MQL5 Types.mqh
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
# All states as a list (for iteration)
# --------------------------------------------------------------------------

ALL_STATES = list(EAState)


# --------------------------------------------------------------------------
# Valid Transition Table
# --------------------------------------------------------------------------
# Mirrors InitTransitionTable() from StateMachine.mqh exactly.
# Each entry is a (from_state, to_state) tuple.

VALID_TRANSITIONS: Set[Tuple[EAState, EAState]] = {
    # BOOT → CONNECT
    (EAState.BOOT, EAState.CONNECT),

    # CONNECT → WAIT_SESSION
    (EAState.CONNECT, EAState.WAIT_SESSION),
    # CONNECT → DISCONNECTED
    (EAState.CONNECT, EAState.DISCONNECTED),

    # WAIT_SESSION → CHECK_RISK
    (EAState.WAIT_SESSION, EAState.CHECK_RISK),

    # CHECK_RISK → SCAN_SIGNAL
    (EAState.CHECK_RISK, EAState.SCAN_SIGNAL),
    # CHECK_RISK → WAIT_SESSION
    (EAState.CHECK_RISK, EAState.WAIT_SESSION),

    # SCAN_SIGNAL → AI_CONFIRMATION
    (EAState.SCAN_SIGNAL, EAState.AI_CONFIRMATION),
    # SCAN_SIGNAL → WAIT_SESSION
    (EAState.SCAN_SIGNAL, EAState.WAIT_SESSION),

    # AI_CONFIRMATION → OPEN_POSITION
    (EAState.AI_CONFIRMATION, EAState.OPEN_POSITION),
    # AI_CONFIRMATION → WAIT_SESSION
    (EAState.AI_CONFIRMATION, EAState.WAIT_SESSION),

    # OPEN_POSITION → MANAGE_POSITION
    (EAState.OPEN_POSITION, EAState.MANAGE_POSITION),

    # MANAGE_POSITION → POSITION_CLOSED
    (EAState.MANAGE_POSITION, EAState.POSITION_CLOSED),

    # POSITION_CLOSED → WAIT_SESSION
    (EAState.POSITION_CLOSED, EAState.WAIT_SESSION),

    # ANY → DISCONNECTED (except DISCONNECTED → DISCONNECTED)
    (EAState.BOOT, EAState.DISCONNECTED),
    (EAState.WAIT_SESSION, EAState.DISCONNECTED),
    (EAState.CHECK_RISK, EAState.DISCONNECTED),
    (EAState.SCAN_SIGNAL, EAState.DISCONNECTED),
    (EAState.AI_CONFIRMATION, EAState.DISCONNECTED),
    (EAState.OPEN_POSITION, EAState.DISCONNECTED),
    (EAState.MANAGE_POSITION, EAState.DISCONNECTED),
    (EAState.POSITION_CLOSED, EAState.DISCONNECTED),

    # DISCONNECTED → WAIT_SESSION
    (EAState.DISCONNECTED, EAState.WAIT_SESSION),
}


# --------------------------------------------------------------------------
# StateMachine class (mirrors CStateMachine)
# --------------------------------------------------------------------------

class StateMachine:
    """
    Python mirror of CStateMachine.

    Implements the same transition validation and state management logic
    as the MQL5 production code.
    """

    def __init__(self):
        self._current_state: EAState = EAState.BOOT

    @property
    def current_state(self) -> EAState:
        """Return current FSM state."""
        return self._current_state

    @current_state.setter
    def current_state(self, state: EAState) -> None:
        """Force-set state (for testing purposes)."""
        self._current_state = state

    def is_valid_transition(self, from_state: EAState, to_state: EAState) -> bool:
        """
        Check if a transition from from_state to to_state is allowed.

        Mirrors CStateMachine::IsValidTransition().
        """
        return (from_state, to_state) in VALID_TRANSITIONS

    def transition_to(self, new_state: EAState, reason: str = "") -> bool:
        """
        Attempt a state transition from current state to new_state.

        Returns True if transition succeeded, False if rejected.
        On rejection, the state remains unchanged.

        Mirrors CStateMachine::TransitionTo().
        """
        if not self.is_valid_transition(self._current_state, new_state):
            return False

        self._current_state = new_state
        return True
