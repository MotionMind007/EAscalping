"""
Property-based tests for HTTP Response Dispatch (Property 5).

Tests cover:
  - 2xx responses with valid JSON → parse JSON
  - 4xx responses → discard without retry
  - 5xx responses → retry with exponential backoff (1s × 2^attempt)
  - Invalid JSON responses → discard without retry regardless of status
  - Backoff calculation correctness

Feature: ea-gateway
Property 5: HTTP Response Dispatch

**Validates: Requirements 2.3, 2.4, 2.5, 2.7**
"""

import json
import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from tests.mirror.http_client import (
    HttpClientDispatch,
    ResponseAction,
    DispatchDecision,
    HTTP_BACKOFF_BASE_MS,
    DEFAULT_MAX_RETRIES,
)


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# Status code ranges
status_2xx = st.integers(min_value=200, max_value=299)
status_4xx = st.integers(min_value=400, max_value=499)
status_5xx = st.integers(min_value=500, max_value=599)
status_any = st.integers(min_value=200, max_value=599)

# Valid JSON bodies
valid_json_objects = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P")),
        min_size=1,
        max_size=20,
    ),
    values=st.one_of(
        st.integers(min_value=-1000, max_value=1000),
        st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        st.text(min_size=0, max_size=50),
        st.booleans(),
        st.none(),
    ),
    min_size=0,
    max_size=10,
).map(json.dumps)

valid_json_arrays = st.lists(
    st.one_of(
        st.integers(min_value=-100, max_value=100),
        st.text(min_size=0, max_size=20),
        st.booleans(),
    ),
    min_size=0,
    max_size=10,
).map(json.dumps)

valid_json_body = st.one_of(valid_json_objects, valid_json_arrays)

# Invalid JSON bodies (not parseable or doesn't start with { or [)
invalid_json_body = st.one_of(
    # Plain text that doesn't start with { or [
    st.text(min_size=1, max_size=100).filter(
        lambda x: x.strip() and x.strip()[0] not in ("{", "[")
    ),
    # Empty strings
    st.just(""),
    # Whitespace only
    st.just("   "),
    # Malformed JSON (starts with { or [ but not valid)
    st.sampled_from([
        "{invalid}",
        "[not json",
        "{'single': 'quotes'}",
        "{missing: quotes}",
        "[1, 2, ]",  # trailing comma
    ]),
)

# Retry attempts
retry_attempts = st.integers(min_value=0, max_value=10)


# --------------------------------------------------------------------------
# Property Tests: 2xx → Parse JSON
# --------------------------------------------------------------------------

class TestResponse2xxParseJson:
    """Property tests: 2xx with valid JSON → PARSE_JSON."""

    @pytest.mark.property
    @given(
        status_code=status_2xx,
        body=valid_json_body,
    )
    def test_2xx_valid_json_parses(self, status_code, body):
        """
        **Validates: Requirements 2.3**

        For any HTTP response with status 2xx and valid JSON body,
        the dispatch SHALL parse the JSON body.
        """
        client = HttpClientDispatch()
        decision = client.dispatch_response(status_code, body)

        assert decision.action == ResponseAction.PARSE_JSON
        assert decision.should_retry is False
        assert decision.parsed_body is not None

    @pytest.mark.property
    @given(
        status_code=status_2xx,
        body=invalid_json_body,
    )
    def test_2xx_invalid_json_discards(self, status_code, body):
        """
        **Validates: Requirements 2.7**

        For any HTTP response with status 2xx but INVALID JSON body,
        the dispatch SHALL discard without retry.
        """
        client = HttpClientDispatch()
        decision = client.dispatch_response(status_code, body)

        assert decision.action == ResponseAction.DISCARD_NO_RETRY
        assert decision.should_retry is False
        assert decision.parsed_body is None


# --------------------------------------------------------------------------
# Property Tests: 4xx → Discard No Retry
# --------------------------------------------------------------------------

class TestResponse4xxDiscard:
    """Property tests: 4xx → discard without retry."""

    @pytest.mark.property
    @given(
        status_code=status_4xx,
        body=valid_json_body,
    )
    def test_4xx_valid_json_discards(self, status_code, body):
        """
        **Validates: Requirements 2.4**

        For any HTTP response with status 4xx (even with valid JSON body),
        the request SHALL be discarded without retry.
        """
        client = HttpClientDispatch()
        decision = client.dispatch_response(status_code, body)

        assert decision.action == ResponseAction.DISCARD_NO_RETRY
        assert decision.should_retry is False

    @pytest.mark.property
    @given(
        status_code=status_4xx,
        body=invalid_json_body,
    )
    def test_4xx_invalid_json_discards(self, status_code, body):
        """
        **Validates: Requirements 2.4, 2.7**

        For any HTTP response with status 4xx and invalid JSON body,
        the request SHALL be discarded without retry.
        """
        client = HttpClientDispatch()
        decision = client.dispatch_response(status_code, body)

        assert decision.action == ResponseAction.DISCARD_NO_RETRY
        assert decision.should_retry is False


# --------------------------------------------------------------------------
# Property Tests: 5xx → Retry with Backoff
# --------------------------------------------------------------------------

class TestResponse5xxRetry:
    """Property tests: 5xx → retry with exponential backoff."""

    @pytest.mark.property
    @given(
        status_code=status_5xx,
        body=valid_json_body,
        attempt=st.integers(min_value=0, max_value=2),  # Below max_retries (3)
    )
    def test_5xx_retries_when_attempts_remain(self, status_code, body, attempt):
        """
        **Validates: Requirements 2.5**

        For any HTTP response with status 5xx and retry attempts remaining,
        the request SHALL be retried with exponential backoff.
        """
        client = HttpClientDispatch(max_retries=DEFAULT_MAX_RETRIES)
        decision = client.dispatch_response(status_code, body, attempt)

        assert decision.action == ResponseAction.RETRY_WITH_BACKOFF
        assert decision.should_retry is True
        expected_backoff = HTTP_BACKOFF_BASE_MS * (2 ** attempt)
        assert decision.backoff_ms == expected_backoff

    @pytest.mark.property
    @given(
        status_code=status_5xx,
        body=valid_json_body,
    )
    def test_5xx_exhausted_after_max_retries(self, status_code, body):
        """
        **Validates: Requirements 2.5**

        For any HTTP response with status 5xx after all retries exhausted,
        the request SHALL be discarded (EXHAUSTED).
        """
        client = HttpClientDispatch(max_retries=DEFAULT_MAX_RETRIES)
        # Attempt == max_retries means all retries used
        decision = client.dispatch_response(status_code, body, attempt=DEFAULT_MAX_RETRIES)

        assert decision.action == ResponseAction.EXHAUSTED
        assert decision.should_retry is False

    @pytest.mark.property
    @given(
        status_code=status_5xx,
        body=invalid_json_body,
        attempt=st.integers(min_value=0, max_value=2),
    )
    def test_5xx_invalid_json_discards_no_retry(self, status_code, body, attempt):
        """
        **Validates: Requirements 2.5, 2.7**

        For any HTTP response with status 5xx but INVALID JSON body,
        the response SHALL be discarded without retry (invalid JSON rule
        takes precedence).
        """
        client = HttpClientDispatch(max_retries=DEFAULT_MAX_RETRIES)
        decision = client.dispatch_response(status_code, body, attempt)

        assert decision.action == ResponseAction.DISCARD_NO_RETRY
        assert decision.should_retry is False


# --------------------------------------------------------------------------
# Property Tests: Backoff Calculation
# --------------------------------------------------------------------------

class TestBackoffCalculation:
    """Property tests for exponential backoff formula."""

    @pytest.mark.property
    @given(attempt=st.integers(min_value=0, max_value=10))
    def test_backoff_is_exponential(self, attempt):
        """
        **Validates: Requirements 2.5**

        For any retry attempt number, the backoff SHALL be 1000ms × 2^attempt.
        """
        client = HttpClientDispatch()
        backoff = client.get_backoff_ms(attempt)

        expected = HTTP_BACKOFF_BASE_MS * (2 ** attempt)
        assert backoff == expected

    @pytest.mark.property
    @given(attempt=st.integers(min_value=1, max_value=10))
    def test_backoff_doubles_each_attempt(self, attempt):
        """
        **Validates: Requirements 2.5**

        For any retry attempt > 0, backoff SHALL be exactly double the
        previous attempt's backoff.
        """
        client = HttpClientDispatch()
        current_backoff = client.get_backoff_ms(attempt)
        previous_backoff = client.get_backoff_ms(attempt - 1)

        assert current_backoff == 2 * previous_backoff


# --------------------------------------------------------------------------
# Property Tests: Invalid JSON Discard Regardless of Status
# --------------------------------------------------------------------------

class TestInvalidJsonAlwaysDiscards:
    """Property tests: invalid JSON → discard regardless of status code."""

    @pytest.mark.property
    @given(
        status_code=status_any,
        body=invalid_json_body,
    )
    def test_invalid_json_always_discards(self, status_code, body):
        """
        **Validates: Requirements 2.7**

        For any HTTP response with invalid JSON body (regardless of status code),
        the response SHALL be discarded without retry.
        """
        client = HttpClientDispatch()
        decision = client.dispatch_response(status_code, body)

        assert decision.action == ResponseAction.DISCARD_NO_RETRY
        assert decision.should_retry is False
        assert decision.parsed_body is None
