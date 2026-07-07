"""
Property-based tests for StateMachine (Task 4.2 - Property 6).

Tests verify that the state machine transition logic matches the specification:
  - Valid transitions succeed
  - Invalid transitions are rejected and state remains unchanged
  - All (state, state) pairs are tested exhaustively

**Validates: Requirements 4.2, 4.3, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.12, 4.13, 4.14, 4.15**

Feature: ea-gateway, Property 6: State Machine Transition Validity
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.mirror.state_machine import (
    EAState,
    StateMachine,
    VALID_TRANSITIONS,
    ALL_STATES,
)


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Generate any valid EAState
ea_states = st.sampled_from(ALL_STATES)

# Generate any (from, to) state pair
state_pairs = st.tuples(ea_states, ea_states)


# --------------------------------------------------------------------------
# Property Tests: State Machine Transition Validity (Property 6)
# --------------------------------------------------------------------------

class TestStateMachineTransitionValidity:
    """
    Property 6: State Machine Transition Validity

    For any current state and any attempted transition, the transition SHALL
    succeed only if the (from, to) pair exists in the valid transitions table.
    All other transitions SHALL be rejected, and the EA SHALL remain in its
    current state.

    **Validates: Requirements 4.2, 4.3, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.12, 4.13, 4.14, 4.15**
    """

    @pytest.mark.property
    @given(from_state=ea_states, to_state=ea_states)
    def test_transition_succeeds_iff_in_valid_table(self, from_state, to_state):
        """
        **Validates: Requirements 4.2, 4.3, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.12, 4.13, 4.14, 4.15**

        For any (from_state, to_state) pair:
        - If (from, to) is in VALID_TRANSITIONS → transition SHALL succeed
        - If (from, to) is NOT in VALID_TRANSITIONS → transition SHALL be rejected
        """
        sm = StateMachine()
        sm.current_state = from_state

        expected_valid = (from_state, to_state) in VALID_TRANSITIONS
        result = sm.transition_to(to_state)

        assert result == expected_valid, (
            f"Transition {from_state.value} → {to_state.value}: "
            f"expected {'valid' if expected_valid else 'invalid'}, "
            f"got {'valid' if result else 'invalid'}"
        )

    @pytest.mark.property
    @given(from_state=ea_states, to_state=ea_states)
    def test_invalid_transition_leaves_state_unchanged(self, from_state, to_state):
        """
        **Validates: Requirements 4.2, 4.3**

        For any invalid (from, to) pair, after a rejected transition attempt,
        the state machine SHALL remain in its original state.
        """
        sm = StateMachine()
        sm.current_state = from_state

        is_valid = (from_state, to_state) in VALID_TRANSITIONS
        sm.transition_to(to_state)

        if not is_valid:
            assert sm.current_state == from_state, (
                f"State changed after invalid transition "
                f"{from_state.value} → {to_state.value}: "
                f"now in {sm.current_state.value}"
            )

    @pytest.mark.property
    @given(from_state=ea_states, to_state=ea_states)
    def test_valid_transition_updates_state(self, from_state, to_state):
        """
        **Validates: Requirements 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.12, 4.13, 4.14, 4.15**

        For any valid (from, to) pair, after a successful transition,
        the state machine SHALL be in the target state.
        """
        sm = StateMachine()
        sm.current_state = from_state

        is_valid = (from_state, to_state) in VALID_TRANSITIONS
        sm.transition_to(to_state)

        if is_valid:
            assert sm.current_state == to_state, (
                f"State not updated after valid transition "
                f"{from_state.value} → {to_state.value}: "
                f"still in {sm.current_state.value}"
            )

    @pytest.mark.property
    @given(from_state=ea_states, to_state=ea_states)
    def test_is_valid_transition_consistent_with_table(self, from_state, to_state):
        """
        **Validates: Requirements 4.2, 4.3**

        The is_valid_transition() query method SHALL return True if and only
        if the (from, to) pair is in the valid transitions table.
        """
        sm = StateMachine()
        expected = (from_state, to_state) in VALID_TRANSITIONS
        result = sm.is_valid_transition(from_state, to_state)

        assert result == expected, (
            f"is_valid_transition({from_state.value}, {to_state.value}) "
            f"returned {result}, expected {expected}"
        )


# --------------------------------------------------------------------------
# Exhaustive Tests: All state pairs (10×10 = 100 combinations)
# --------------------------------------------------------------------------

class TestStateMachineExhaustive:
    """
    Exhaustive check of all 100 state pair combinations.

    This complements the property tests by ensuring every single combination
    is explicitly verified against the transition table.
    """

    @pytest.mark.property
    @pytest.mark.parametrize(
        "from_state,to_state",
        [(f, t) for f in ALL_STATES for t in ALL_STATES],
        ids=[f"{f.value}->{t.value}" for f in ALL_STATES for t in ALL_STATES],
    )
    def test_all_state_pairs(self, from_state, to_state):
        """
        **Validates: Requirements 4.2, 4.3, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.12, 4.13, 4.14, 4.15**

        For each of the 100 (from, to) combinations, verify transition
        result matches the specification table exactly.
        """
        sm = StateMachine()
        sm.current_state = from_state

        expected_valid = (from_state, to_state) in VALID_TRANSITIONS
        result = sm.transition_to(to_state)

        assert result == expected_valid, (
            f"Transition {from_state.value} → {to_state.value}: "
            f"expected {'VALID' if expected_valid else 'INVALID'}, "
            f"got {'VALID' if result else 'INVALID'}"
        )

        # Verify post-condition: state is correct
        if expected_valid:
            assert sm.current_state == to_state
        else:
            assert sm.current_state == from_state


# --------------------------------------------------------------------------
# Specific transition table validation
# --------------------------------------------------------------------------

class TestTransitionTableCompleteness:
    """
    Validates that the VALID_TRANSITIONS table matches the spec exactly.

    Ensures no transitions are missing or extra compared to the design doc.
    """

    def test_disconnected_self_transition_invalid(self):
        """
        **Validates: Requirements 4.2**

        DISCONNECTED → DISCONNECTED is explicitly excluded from valid transitions.
        """
        assert (EAState.DISCONNECTED, EAState.DISCONNECTED) not in VALID_TRANSITIONS

    def test_any_state_can_reach_disconnected(self):
        """
        **Validates: Requirements 4.14**

        Every state except DISCONNECTED itself can transition to DISCONNECTED.
        """
        for state in ALL_STATES:
            if state == EAState.DISCONNECTED:
                assert (state, EAState.DISCONNECTED) not in VALID_TRANSITIONS
            else:
                assert (state, EAState.DISCONNECTED) in VALID_TRANSITIONS, (
                    f"{state.value} → DISCONNECTED should be valid"
                )

    def test_disconnected_can_reconnect(self):
        """
        **Validates: Requirements 4.15**

        DISCONNECTED → WAIT_SESSION is a valid transition (reconnection).
        """
        assert (EAState.DISCONNECTED, EAState.WAIT_SESSION) in VALID_TRANSITIONS

    def test_boot_only_goes_to_connect(self):
        """
        **Validates: Requirements 4.5**

        BOOT can only transition to CONNECT (and DISCONNECTED via ANY rule).
        """
        for target in ALL_STATES:
            if target in (EAState.CONNECT, EAState.DISCONNECTED):
                assert (EAState.BOOT, target) in VALID_TRANSITIONS
            else:
                assert (EAState.BOOT, target) not in VALID_TRANSITIONS, (
                    f"BOOT → {target.value} should NOT be valid"
                )

    def test_total_valid_transition_count(self):
        """
        **Validates: Requirements 4.2**

        The transition table should have exactly the expected number of entries.

        Count:
        - Explicit named transitions: 13
          (BOOT→CONNECT, CONNECT→WAIT_SESSION, CONNECT→DISCONNECTED,
           WAIT_SESSION→CHECK_RISK, CHECK_RISK→SCAN_SIGNAL, CHECK_RISK→WAIT_SESSION,
           SCAN_SIGNAL→AI_CONFIRMATION, SCAN_SIGNAL→WAIT_SESSION,
           AI_CONFIRMATION→OPEN_POSITION, AI_CONFIRMATION→WAIT_SESSION,
           OPEN_POSITION→MANAGE_POSITION, MANAGE_POSITION→POSITION_CLOSED,
           POSITION_CLOSED→WAIT_SESSION)
        - ANY→DISCONNECTED: 9 states (all except DISCONNECTED itself)
          But CONNECT→DISCONNECTED and BOOT→DISCONNECTED are already counted above.
          Additional: WAIT_SESSION, CHECK_RISK, SCAN_SIGNAL, AI_CONFIRMATION,
                      OPEN_POSITION, MANAGE_POSITION, POSITION_CLOSED → DISCONNECTED = 7 new
        - DISCONNECTED→WAIT_SESSION: 1

        Total unique: 13 + 7 + 1 = 21
        But CONNECT→DISCONNECTED is in both lists, so: 13 (named) + 7 (ANY rule extras) + 1 = 21
        Actually: let's count the set directly.
        """
        # The expected count based on the MQL5 transition table:
        # 13 explicit named transitions + 8 additional ANY→DISCONNECTED
        # (BOOT, WAIT_SESSION, CHECK_RISK, SCAN_SIGNAL, AI_CONFIRMATION,
        #  OPEN_POSITION, MANAGE_POSITION, POSITION_CLOSED → DISCONNECTED,
        #  since CONNECT→DISCONNECTED is already in the 13 named)
        # + 1 DISCONNECTED→WAIT_SESSION = 22 total
        expected_count = 22
        assert len(VALID_TRANSITIONS) == expected_count, (
            f"Expected {expected_count} valid transitions, "
            f"got {len(VALID_TRANSITIONS)}"
        )
