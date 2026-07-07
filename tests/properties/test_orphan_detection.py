"""
Property-based tests for Orphan Position Detection (Property 13).

**Validates: Requirements 7.4, 7.6**

Property: *For any* set of MT5 open positions and any set of backend-known positions,
a position SHALL be identified as an orphan if and only if it exists in the MT5 set
but NOT in the backend-known set. All orphan positions SHALL be reported to the backend.

Feature: ea-gateway, Property 13: Orphan Position Detection
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from tests.mirror.orphan_detector import OrphanDetector, Position


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Ticket numbers: realistic range for MT5 position tickets
ticket_numbers = st.integers(min_value=1, max_value=999_999_999)

# Sets of ticket numbers (simulating positions)
position_sets = st.frozensets(ticket_numbers, min_size=0, max_size=20)

# Position details for detailed orphan detection
directions = st.sampled_from(["BUY", "SELL"])
lot_sizes = st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False)
prices = st.floats(min_value=1000.0, max_value=3000.0, allow_nan=False, allow_infinity=False)

position_objects = st.builds(
    Position,
    ticket=ticket_numbers,
    symbol=st.just("XAUUSD"),
    direction=directions,
    lot_size=lot_sizes,
    open_price=prices,
)

position_lists = st.lists(position_objects, min_size=0, max_size=20, unique_by=lambda p: p.ticket)


# --------------------------------------------------------------------------
# Property Tests
# --------------------------------------------------------------------------

class TestOrphanPositionDetection:
    """Property 13: Orphan Position Detection."""

    @pytest.mark.property
    @given(
        mt5_tickets=position_sets,
        backend_tickets=position_sets,
    )
    def test_orphans_equals_set_difference(self, mt5_tickets, backend_tickets):
        """
        **Validates: Requirements 7.4, 7.6**

        For any two sets of positions, orphans SHALL equal MT5_set - backend_set.
        """
        detector = OrphanDetector()
        mt5_set = set(mt5_tickets)
        backend_set = set(backend_tickets)

        orphans = detector.detect_orphans(mt5_set, backend_set)

        expected = mt5_set - backend_set
        assert orphans == expected, (
            f"Orphans mismatch. Got: {orphans}, Expected: {expected}"
        )

    @pytest.mark.property
    @given(
        mt5_tickets=position_sets,
        backend_tickets=position_sets,
    )
    def test_orphan_exists_in_mt5_not_in_backend(self, mt5_tickets, backend_tickets):
        """
        **Validates: Requirements 7.4, 7.6**

        For any detected orphan, it SHALL exist in the MT5 set
        AND shall NOT exist in the backend set.
        """
        detector = OrphanDetector()
        mt5_set = set(mt5_tickets)
        backend_set = set(backend_tickets)

        orphans = detector.detect_orphans(mt5_set, backend_set)

        for ticket in orphans:
            assert ticket in mt5_set, (
                f"Orphan ticket {ticket} not found in MT5 positions"
            )
            assert ticket not in backend_set, (
                f"Orphan ticket {ticket} should NOT be in backend positions"
            )

    @pytest.mark.property
    @given(
        mt5_tickets=position_sets,
        backend_tickets=position_sets,
    )
    def test_all_orphans_reported(self, mt5_tickets, backend_tickets):
        """
        **Validates: Requirements 7.4, 7.6**

        For any two sets, ALL orphan positions SHALL be reported.
        No orphan shall be missed.
        """
        detector = OrphanDetector()
        mt5_set = set(mt5_tickets)
        backend_set = set(backend_tickets)

        orphans = detector.detect_orphans(mt5_set, backend_set)

        # Simulate reporting: all detected orphans are reported
        reported = orphans.copy()

        assert detector.all_orphans_reported(mt5_set, backend_set, reported), (
            "Not all orphans were reported"
        )

    @pytest.mark.property
    @given(
        mt5_tickets=position_sets,
        backend_tickets=position_sets,
    )
    def test_non_orphan_positions_not_reported(self, mt5_tickets, backend_tickets):
        """
        **Validates: Requirements 7.4, 7.6**

        For any position that exists in BOTH MT5 and backend sets,
        it SHALL NOT be identified as an orphan.
        """
        detector = OrphanDetector()
        mt5_set = set(mt5_tickets)
        backend_set = set(backend_tickets)

        orphans = detector.detect_orphans(mt5_set, backend_set)

        # Positions in both sets should never be orphans
        common_positions = mt5_set & backend_set
        for ticket in common_positions:
            assert ticket not in orphans, (
                f"Ticket {ticket} exists in both sets but was reported as orphan"
            )

    @pytest.mark.property
    @given(
        mt5_tickets=position_sets,
        backend_tickets=position_sets,
    )
    def test_backend_only_positions_not_orphans(self, mt5_tickets, backend_tickets):
        """
        **Validates: Requirements 7.4, 7.6**

        Positions that exist ONLY in the backend set (not in MT5)
        SHALL NOT be identified as orphans.
        """
        detector = OrphanDetector()
        mt5_set = set(mt5_tickets)
        backend_set = set(backend_tickets)

        orphans = detector.detect_orphans(mt5_set, backend_set)

        # Backend-only positions are not orphans
        backend_only = backend_set - mt5_set
        for ticket in backend_only:
            assert ticket not in orphans, (
                f"Backend-only ticket {ticket} should not be reported as orphan"
            )

    @pytest.mark.property
    @given(positions=position_lists, backend_tickets=position_sets)
    def test_detailed_orphan_detection_matches_set_logic(self, positions, backend_tickets):
        """
        **Validates: Requirements 7.4, 7.6**

        For any list of Position objects and backend-known tickets,
        detailed orphan detection SHALL produce the same orphan tickets
        as the simple set difference.
        """
        detector = OrphanDetector()
        backend_set = set(backend_tickets)

        # Detect using detailed method
        detailed_orphans = detector.detect_orphans_with_details(positions, backend_set)
        detailed_tickets = {pos.ticket for pos in detailed_orphans}

        # Detect using simple set method
        mt5_set = {pos.ticket for pos in positions}
        simple_orphans = detector.detect_orphans(mt5_set, backend_set)

        assert detailed_tickets == simple_orphans, (
            f"Detailed and simple orphan detection disagree. "
            f"Detailed: {detailed_tickets}, Simple: {simple_orphans}"
        )

    @pytest.mark.property
    @given(shared_tickets=position_sets)
    def test_no_orphans_when_sets_equal(self, shared_tickets):
        """
        **Validates: Requirements 7.4, 7.6**

        When MT5 and backend have exactly the same positions,
        there SHALL be zero orphans detected.
        """
        detector = OrphanDetector()
        shared_set = set(shared_tickets)

        orphans = detector.detect_orphans(shared_set, shared_set.copy())

        assert len(orphans) == 0, (
            f"Expected no orphans when sets are equal, got: {orphans}"
        )

    @pytest.mark.property
    @given(mt5_tickets=st.frozensets(ticket_numbers, min_size=1, max_size=20))
    def test_all_orphans_when_backend_empty(self, mt5_tickets):
        """
        **Validates: Requirements 7.4, 7.6**

        When the backend has no known positions (empty set),
        ALL MT5 positions SHALL be identified as orphans.
        """
        detector = OrphanDetector()
        mt5_set = set(mt5_tickets)
        empty_backend = set()

        orphans = detector.detect_orphans(mt5_set, empty_backend)

        assert orphans == mt5_set, (
            f"All positions should be orphans when backend is empty. "
            f"Got: {orphans}, Expected: {mt5_set}"
        )
