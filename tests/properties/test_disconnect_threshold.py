"""
Property-based tests for Disconnection Threshold (Property 12).

**Validates: Requirements 7.2**

Property: *For any* sequence of N consecutive connection failures, the EA SHALL enter
DISCONNECTED state if and only if the failure count reaches exactly 10. At fewer than
10 consecutive failures, the EA SHALL remain in its current state and retry.

Feature: ea-gateway, Property 12: Disconnection Threshold
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from dataclasses import dataclass
from enum import Enum
from typing import List


# --------------------------------------------------------------------------
# Mirror implementation for disconnection threshold logic
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


# States that can transition to DISCONNECTED (any state except BOOT)
CONNECTABLE_STATES = [
    EAState.CONNECT,
    EAState.WAIT_SESSION,
    EAState.CHECK_RISK,
    EAState.SCAN_SIGNAL,
    EAState.AI_CONFIRMATION,
    EAState.OPEN_POSITION,
    EAState.MANAGE_POSITION,
    EAState.POSITION_CLOSED,
]

# The threshold for entering DISCONNECTED state
DISCONNECT_THRESHOLD = 10


class ConnectionMonitor:
    """
    Python mirror of the disconnection threshold logic in CStateMachine / CHttpClient.

    After 10 consecutive connection failures, the EA enters DISCONNECTED state.
    Fewer than 10 failures: EA remains in its current state and retries.
    A single success resets the failure counter.

    Mirrors the reconnection protocol from the design document:
    - After 3 retries exhausted (5xx) or connection timeout → reconnection loop
    - After 10 consecutive failures in reconnection loop → DISCONNECTED state
    """

    def __init__(self, initial_state: EAState = EAState.WAIT_SESSION):
        self.current_state = initial_state
        self.consecutive_failures = 0

    def record_failure(self) -> EAState:
        """
        Record a connection failure and return the resulting state.

        If consecutive failures reach DISCONNECT_THRESHOLD (10),
        transitions to DISCONNECTED state.
        Otherwise, remains in current state.
        """
        self.consecutive_failures += 1

        if self.consecutive_failures >= DISCONNECT_THRESHOLD:
            self.current_state = EAState.DISCONNECTED

        return self.current_state

    def record_success(self) -> EAState:
        """
        Record a successful connection, resetting the failure counter.

        Returns the current state (unchanged by success).
        """
        self.consecutive_failures = 0
        return self.current_state

    def process_failure_sequence(self, count: int) -> EAState:
        """
        Process a sequence of consecutive failures.

        Args:
            count: Number of consecutive failures to process

        Returns:
            The EA state after processing all failures
        """
        for _ in range(count):
            self.record_failure()
        return self.current_state


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------

connectable_states = st.sampled_from(CONNECTABLE_STATES)

# Failure counts that should NOT trigger disconnection (1-9)
sub_threshold_counts = st.integers(min_value=1, max_value=DISCONNECT_THRESHOLD - 1)

# Failure counts that SHOULD trigger disconnection (10-15)
at_or_above_threshold_counts = st.integers(min_value=DISCONNECT_THRESHOLD, max_value=15)

# Any failure count for general testing
any_failure_count = st.integers(min_value=1, max_value=15)


# --------------------------------------------------------------------------
# Property Tests
# --------------------------------------------------------------------------

class TestDisconnectionThreshold:
    """Property 12: Disconnection Threshold."""

    @pytest.mark.property
    @given(
        initial_state=connectable_states,
        failure_count=at_or_above_threshold_counts,
    )
    def test_disconnected_entered_at_threshold(self, initial_state, failure_count):
        """
        **Validates: Requirements 7.2**

        For any N >= 10 consecutive failures, the EA SHALL enter DISCONNECTED state.
        """
        monitor = ConnectionMonitor(initial_state)
        final_state = monitor.process_failure_sequence(failure_count)

        assert final_state == EAState.DISCONNECTED, (
            f"Expected DISCONNECTED after {failure_count} failures from {initial_state.value}, "
            f"got {final_state.value}"
        )

    @pytest.mark.property
    @given(
        initial_state=connectable_states,
        failure_count=sub_threshold_counts,
    )
    def test_remains_in_current_state_below_threshold(self, initial_state, failure_count):
        """
        **Validates: Requirements 7.2**

        For any N < 10 consecutive failures, the EA SHALL remain in its current state.
        """
        monitor = ConnectionMonitor(initial_state)
        final_state = monitor.process_failure_sequence(failure_count)

        assert final_state == initial_state, (
            f"Expected to remain in {initial_state.value} after {failure_count} failures, "
            f"got {final_state.value}"
        )

    @pytest.mark.property
    @given(
        initial_state=connectable_states,
        failures_before_success=sub_threshold_counts,
        failures_after_success=sub_threshold_counts,
    )
    def test_success_resets_failure_counter(self, initial_state,
                                            failures_before_success,
                                            failures_after_success):
        """
        **Validates: Requirements 7.2**

        For any sequence where a success occurs between failures,
        the counter SHALL reset. If neither sub-sequence alone reaches 10,
        DISCONNECTED shall NOT be entered.
        """
        monitor = ConnectionMonitor(initial_state)

        # Apply first batch of failures (< 10)
        monitor.process_failure_sequence(failures_before_success)
        assert monitor.current_state == initial_state

        # A success resets the counter
        monitor.record_success()
        assert monitor.consecutive_failures == 0

        # Apply second batch of failures (< 10)
        monitor.process_failure_sequence(failures_after_success)

        assert monitor.current_state == initial_state, (
            f"Expected to remain in {initial_state.value} after reset. "
            f"Failures before: {failures_before_success}, after: {failures_after_success}"
        )

    @pytest.mark.property
    @given(initial_state=connectable_states)
    def test_exactly_10_failures_triggers_disconnection(self, initial_state):
        """
        **Validates: Requirements 7.2**

        For exactly 10 consecutive failures, the EA SHALL enter DISCONNECTED state
        on the 10th failure (not before).
        """
        monitor = ConnectionMonitor(initial_state)

        # First 9 failures: should remain in current state
        for i in range(1, DISCONNECT_THRESHOLD):
            monitor.record_failure()
            assert monitor.current_state == initial_state, (
                f"Prematurely entered DISCONNECTED at failure #{i}"
            )

        # 10th failure: should now be DISCONNECTED
        monitor.record_failure()
        assert monitor.current_state == EAState.DISCONNECTED, (
            f"Did not enter DISCONNECTED on failure #{DISCONNECT_THRESHOLD}"
        )

    @pytest.mark.property
    @given(
        initial_state=connectable_states,
        failure_count=any_failure_count,
    )
    def test_disconnection_iff_threshold_reached(self, initial_state, failure_count):
        """
        **Validates: Requirements 7.2**

        For any N consecutive failures, DISCONNECTED is entered if and only if N >= 10.
        This is the bidirectional property.
        """
        monitor = ConnectionMonitor(initial_state)
        final_state = monitor.process_failure_sequence(failure_count)

        if failure_count >= DISCONNECT_THRESHOLD:
            assert final_state == EAState.DISCONNECTED, (
                f"Should be DISCONNECTED after {failure_count} failures"
            )
        else:
            assert final_state != EAState.DISCONNECTED, (
                f"Should NOT be DISCONNECTED after only {failure_count} failures"
            )
