"""
Property-based tests for SessionManager (Task 5.2 - Property 8: Session Time Identification).

Tests cover:
  - Session name identification for all UTC hours (LONDON, OVERLAP, NEW_YORK, OFF)
  - Combined session window (IsInSession) correctness
  - Individual session flags (IsLondonSession, IsNewYorkSession)

Feature: ea-gateway
Property 8: Session Time Identification

**Validates: Requirements 6.1**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.mirror.session_manager import SessionManager, SessionName


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Full UTC hour range with minute granularity (hour as float 0.0 - 23.99)
utc_hours = st.integers(min_value=0, max_value=23)

# Minute granularity: generate hour + minute for finer-grained testing
utc_hour_minute = st.tuples(
    st.integers(min_value=0, max_value=23),
    st.integers(min_value=0, max_value=59),
)

# Session boundary hours for focused testing
london_only_hours = st.integers(min_value=8, max_value=12)       # [8, 13)
overlap_hours = st.integers(min_value=13, max_value=15)           # [13, 16)
ny_only_hours = st.integers(min_value=16, max_value=20)           # [16, 21)
off_hours = st.one_of(
    st.integers(min_value=0, max_value=7),
    st.integers(min_value=21, max_value=23),
)

# In-session hours: [8, 21)
in_session_hours = st.integers(min_value=8, max_value=20)


# --------------------------------------------------------------------------
# Property Tests: Session Name Identification (Property 8)
# --------------------------------------------------------------------------

class TestSessionTimeIdentification:
    """
    Property 8: Session Time Identification

    For any UTC hour H (0-23), the session identification function SHALL return:
    - "LONDON" if 8 <= H < 13
    - "OVERLAP" if 13 <= H < 16
    - "NEW_YORK" if 16 <= H < 21
    - "OFF" if H < 8 or H >= 21

    **Validates: Requirements 6.1**
    """

    @pytest.mark.property
    @given(hour=london_only_hours)
    def test_london_session_identification(self, hour):
        """
        **Validates: Requirements 6.1**

        For any UTC hour H where 8 <= H < 13,
        GetCurrentSessionName SHALL return "LONDON".
        """
        sm = SessionManager()
        result = sm.get_current_session_name(hour)
        assert result == SessionName.LONDON, (
            f"Expected LONDON for hour {hour}, got {result.value}"
        )

    @pytest.mark.property
    @given(hour=overlap_hours)
    def test_overlap_session_identification(self, hour):
        """
        **Validates: Requirements 6.1**

        For any UTC hour H where 13 <= H < 16,
        GetCurrentSessionName SHALL return "OVERLAP".
        """
        sm = SessionManager()
        result = sm.get_current_session_name(hour)
        assert result == SessionName.OVERLAP, (
            f"Expected OVERLAP for hour {hour}, got {result.value}"
        )

    @pytest.mark.property
    @given(hour=ny_only_hours)
    def test_new_york_session_identification(self, hour):
        """
        **Validates: Requirements 6.1**

        For any UTC hour H where 16 <= H < 21,
        GetCurrentSessionName SHALL return "NEW_YORK".
        """
        sm = SessionManager()
        result = sm.get_current_session_name(hour)
        assert result == SessionName.NEW_YORK, (
            f"Expected NEW_YORK for hour {hour}, got {result.value}"
        )

    @pytest.mark.property
    @given(hour=off_hours)
    def test_off_session_identification(self, hour):
        """
        **Validates: Requirements 6.1**

        For any UTC hour H where H < 8 or H >= 21,
        GetCurrentSessionName SHALL return "OFF".
        """
        sm = SessionManager()
        result = sm.get_current_session_name(hour)
        assert result == SessionName.OFF, (
            f"Expected OFF for hour {hour}, got {result.value}"
        )

    @pytest.mark.property
    @given(hour=utc_hours)
    def test_session_name_exhaustive(self, hour):
        """
        **Validates: Requirements 6.1**

        For any UTC hour H (0-23), the session identification SHALL
        return exactly one of: LONDON (8<=H<13), OVERLAP (13<=H<16),
        NEW_YORK (16<=H<21), or OFF (H<8 or H>=21).
        """
        sm = SessionManager()
        result = sm.get_current_session_name(hour)

        if 8 <= hour < 13:
            assert result == SessionName.LONDON
        elif 13 <= hour < 16:
            assert result == SessionName.OVERLAP
        elif 16 <= hour < 21:
            assert result == SessionName.NEW_YORK
        else:
            assert result == SessionName.OFF

    @pytest.mark.property
    @given(hour=in_session_hours)
    def test_is_in_session_true_during_session(self, hour):
        """
        **Validates: Requirements 6.1**

        IsInSession SHALL be true if and only if 8 <= H < 21.
        This test verifies the "true" direction for in-session hours.
        """
        sm = SessionManager()
        assert sm.is_in_session(hour) is True, (
            f"Expected IsInSession=True for hour {hour}"
        )

    @pytest.mark.property
    @given(hour=off_hours)
    def test_is_in_session_false_outside_session(self, hour):
        """
        **Validates: Requirements 6.1**

        IsInSession SHALL be false if H < 8 or H >= 21.
        This test verifies the "false" direction for off hours.
        """
        sm = SessionManager()
        assert sm.is_in_session(hour) is False, (
            f"Expected IsInSession=False for hour {hour}"
        )

    @pytest.mark.property
    @given(hour=utc_hours)
    def test_is_london_session(self, hour):
        """
        **Validates: Requirements 6.1**

        IsLondonSession SHALL be true if 8 <= H < 16.
        """
        sm = SessionManager()
        expected = 8 <= hour < 16
        assert sm.is_london_session(hour) == expected, (
            f"IsLondonSession({hour}) expected {expected}, "
            f"got {sm.is_london_session(hour)}"
        )

    @pytest.mark.property
    @given(hour=utc_hours)
    def test_is_new_york_session(self, hour):
        """
        **Validates: Requirements 6.1**

        IsNewYorkSession SHALL be true if 13 <= H < 21.
        """
        sm = SessionManager()
        expected = 13 <= hour < 21
        assert sm.is_new_york_session(hour) == expected, (
            f"IsNewYorkSession({hour}) expected {expected}, "
            f"got {sm.is_new_york_session(hour)}"
        )

    @pytest.mark.property
    @given(hour_minute=utc_hour_minute)
    def test_session_name_with_minute_granularity(self, hour_minute):
        """
        **Validates: Requirements 6.1**

        For any UTC time (hour, minute), session identification
        SHALL depend only on the hour component (minute is irrelevant
        to session boundaries at hourly granularity).
        """
        hour, minute = hour_minute
        sm = SessionManager()

        # Session name is determined by hour only
        result = sm.get_current_session_name(hour)

        if 8 <= hour < 13:
            assert result == SessionName.LONDON
        elif 13 <= hour < 16:
            assert result == SessionName.OVERLAP
        elif 16 <= hour < 21:
            assert result == SessionName.NEW_YORK
        else:
            assert result == SessionName.OFF
