"""
Property-based tests for Payload Timestamp Format (Property 2).

Property 2: Payload Timestamp Format
  *For any* datetime, the formatted timestamp SHALL match the pattern
  `\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}Z`

Feature: ea-gateway, Property 2: Payload Timestamp Format
**Validates: Requirements 1.5**
"""

import re
from datetime import datetime, timezone, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


# --------------------------------------------------------------------------
# Timestamp formatting function (mirrors MQL5 timestamp serialization)
# --------------------------------------------------------------------------

def format_timestamp_utc(dt: datetime) -> str:
    """
    Format a datetime as ISO 8601 UTC string matching the EA's format:
    yyyy-MM-ddTHH:mm:ss.fffZ

    This mirrors the timestamp serialization used in MarketCollector
    and all EA HTTP payloads.
    """
    # Ensure we're working in UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    # Format with millisecond precision and Z suffix
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


# --------------------------------------------------------------------------
# The expected pattern
# --------------------------------------------------------------------------

TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Generate datetime values within a realistic range for trading
# From year 2000 to 2099, covering all months/days/hours/minutes/seconds/ms
realistic_datetimes = st.datetimes(
    min_value=datetime(2000, 1, 1, 0, 0, 0),
    max_value=datetime(2099, 12, 31, 23, 59, 59),
    timezones=st.just(timezone.utc),
)

# Generate datetimes with various microsecond values to test millisecond truncation
datetimes_with_microseconds = st.builds(
    lambda dt, us: dt.replace(microsecond=us),
    realistic_datetimes,
    st.integers(min_value=0, max_value=999999),
)

# Generate datetimes from non-UTC timezones to test UTC conversion
non_utc_offsets = st.integers(min_value=-12, max_value=12).map(
    lambda h: timezone(timedelta(hours=h))
)

non_utc_datetimes = st.builds(
    lambda dt, tz: dt.replace(tzinfo=tz),
    st.datetimes(
        min_value=datetime(2000, 1, 1, 0, 0, 0),
        max_value=datetime(2099, 12, 31, 23, 59, 59),
    ),
    non_utc_offsets,
)


# --------------------------------------------------------------------------
# Property Tests: Payload Timestamp Format
# --------------------------------------------------------------------------

class TestTimestampFormat:
    """Property 2: Payload Timestamp Format."""

    @pytest.mark.property
    @given(dt=realistic_datetimes)
    def test_utc_timestamp_matches_pattern(self, dt):
        """
        **Validates: Requirements 1.5**

        For any UTC datetime, the formatted timestamp SHALL match
        the pattern yyyy-MM-ddTHH:mm:ss.fffZ.
        """
        result = format_timestamp_utc(dt)
        assert TIMESTAMP_PATTERN.match(result), (
            f"Timestamp '{result}' does not match expected pattern"
        )

    @pytest.mark.property
    @given(dt=datetimes_with_microseconds)
    def test_microseconds_truncated_to_milliseconds(self, dt):
        """
        **Validates: Requirements 1.5**

        For any datetime with arbitrary microseconds, the formatted
        timestamp SHALL contain exactly 3 digits for the fractional
        second (milliseconds), truncating any sub-millisecond precision.
        """
        result = format_timestamp_utc(dt)
        assert TIMESTAMP_PATTERN.match(result), (
            f"Timestamp '{result}' does not match expected pattern"
        )

        # Extract millisecond part and verify it's correct
        ms_part = result.split(".")[1].rstrip("Z")
        assert len(ms_part) == 3
        expected_ms = dt.microsecond // 1000
        assert int(ms_part) == expected_ms

    @pytest.mark.property
    @given(dt=non_utc_datetimes)
    def test_non_utc_converted_and_matches_pattern(self, dt):
        """
        **Validates: Requirements 1.5**

        For any datetime in a non-UTC timezone, the formatted timestamp
        SHALL be converted to UTC and match the pattern yyyy-MM-ddTHH:mm:ss.fffZ.
        """
        result = format_timestamp_utc(dt)
        assert TIMESTAMP_PATTERN.match(result), (
            f"Timestamp '{result}' does not match expected pattern"
        )

    @pytest.mark.property
    @given(dt=realistic_datetimes)
    def test_timestamp_ends_with_z(self, dt):
        """
        **Validates: Requirements 1.5**

        For any datetime, the formatted timestamp SHALL always end
        with 'Z' indicating UTC timezone.
        """
        result = format_timestamp_utc(dt)
        assert result.endswith("Z"), f"Timestamp '{result}' does not end with Z"

    @pytest.mark.property
    @given(dt=realistic_datetimes)
    def test_timestamp_has_t_separator(self, dt):
        """
        **Validates: Requirements 1.5**

        For any datetime, the formatted timestamp SHALL contain a 'T'
        separator between date and time components.
        """
        result = format_timestamp_utc(dt)
        assert "T" in result, f"Timestamp '{result}' missing T separator"
        parts = result.split("T")
        assert len(parts) == 2

    @pytest.mark.property
    @given(dt=realistic_datetimes)
    def test_timestamp_length_is_fixed(self, dt):
        """
        **Validates: Requirements 1.5**

        For any datetime, the formatted timestamp SHALL always be
        exactly 24 characters long (yyyy-MM-ddTHH:mm:ss.fffZ).
        """
        result = format_timestamp_utc(dt)
        assert len(result) == 24, (
            f"Timestamp '{result}' has length {len(result)}, expected 24"
        )
