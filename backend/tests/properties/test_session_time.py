"""Property-based tests for is_in_session function.

Tests verify the session time evaluation logic for the backend gateway.

Requirements: 2.4, 4.4
"""

import os
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Set required env vars before importing Settings
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AUTH_TOKEN", "test-token-secret")

from app.config import Settings
from app.services.signal_engine import is_in_session


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Full UTC hour range
utc_hours = st.integers(min_value=0, max_value=23)

# Session boundary hours for focused testing
in_session_hours = st.integers(min_value=8, max_value=20)  # [8, 21)
off_hours = st.one_of(
    st.integers(min_value=0, max_value=7),
    st.integers(min_value=21, max_value=23),
)

# Specific edge case hours
edge_case_hours = st.sampled_from([7, 8, 20, 21])


# --------------------------------------------------------------------------
# Property Tests: is_in_session
# --------------------------------------------------------------------------

class TestIsInSessionProperty:
    """
    Property-based tests for is_in_session function.

    **Validates: Requirements 2.4, 4.4**

    The function returns True if and only if the UTC hour is within
    the combined trading session window [8, 21), which covers:
    - London session: [8, 16)
    - New York session: [13, 21)
    - Combined: [8, 21)
    """

    @pytest.mark.property
    @settings(deadline=None, max_examples=100)
    @given(hour=in_session_hours)
    def test_is_in_session_true_during_session(self, hour):
        """
        **Validates: Requirements 2.4, 4.4**

        For any UTC hour H where 8 <= H < 21, is_in_session SHALL return True.
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, hour, 30, 0, tzinfo=timezone.utc)
        assert is_in_session(dt, settings) is True, (
            f"Expected is_in_session=True for hour {hour}"
        )

    @pytest.mark.property
    @settings(deadline=None, max_examples=100)
    @given(hour=off_hours)
    def test_is_in_session_false_outside_session(self, hour):
        """
        **Validates: Requirements 2.4, 4.4**

        For any UTC hour H where H < 8 or H >= 21, is_in_session SHALL return False.
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, hour, 30, 0, tzinfo=timezone.utc)
        assert is_in_session(dt, settings) is False, (
            f"Expected is_in_session=False for hour {hour}"
        )

    @pytest.mark.property
    @settings(deadline=None, max_examples=100)
    @given(hour=utc_hours)
    def test_is_in_session_exhaustive(self, hour):
        """
        **Validates: Requirements 2.4, 4.4**

        For any UTC hour H (0-23), is_in_session SHALL return True
        if and only if 8 <= H < 21.
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, hour, 30, 0, tzinfo=timezone.utc)
        expected = 8 <= hour < 21
        result = is_in_session(dt, settings)
        assert result == expected, (
            f"Hour {hour}: expected is_in_session={expected}, got {result}"
        )

    @pytest.mark.property
    @settings(deadline=None, max_examples=100)
    @given(hour=utc_hours, minute=st.integers(min_value=0, max_value=59))
    def test_is_in_session_with_minute_granularity(self, hour, minute):
        """
        **Validates: Requirements 2.4, 4.4**

        For any UTC time (hour, minute), session evaluation SHALL
        depend only on the hour component (minute is irrelevant
        to session boundaries at hourly granularity).
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, hour, minute, 0, tzinfo=timezone.utc)
        expected = 8 <= hour < 21
        result = is_in_session(dt, settings)
        assert result == expected, (
            f"Hour {hour}, minute {minute}: expected is_in_session={expected}, got {result}"
        )


class TestIsInSessionEdgeCases:
    """
    Edge case tests for is_in_session function.

    Verifies boundary conditions at session start and end.
    """

    def test_edge_hour_7_before_london(self):
        """
        Hour 7 is 1 hour before London session start (8).
        Expected: False
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, 7, 0, 0, tzinfo=timezone.utc)
        assert is_in_session(dt, settings) is False

    def test_edge_hour_8_london_start(self):
        """
        Hour 8 is the start of London session (inclusive).
        Expected: True
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        assert is_in_session(dt, settings) is True

    def test_edge_hour_20_within_ny(self):
        """
        Hour 20 is within NY session (13-21).
        Expected: True
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, 20, 0, 0, tzinfo=timezone.utc)
        assert is_in_session(dt, settings) is True

    def test_edge_hour_21_ny_end(self):
        """
        Hour 21 is the end of NY session (exclusive).
        Expected: False
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, 21, 0, 0, tzinfo=timezone.utc)
        assert is_in_session(dt, settings) is False

    def test_overlap_hour_14_both_sessions(self):
        """
        Hour 14 is within both London and NY sessions (overlap).
        Expected: True
        """
        settings = Settings()
        dt = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        assert is_in_session(dt, settings) is True
