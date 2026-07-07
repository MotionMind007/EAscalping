"""
Property-based tests for ConfigManager (Task 2.2).

Property 14: Configuration Parameter Validation

For any configuration input value:
- Backend URL SHALL be accepted only if it is a well-formed HTTP or HTTPS URL
  with length <= 2048 characters
- Auth token SHALL be accepted only if non-empty with length <= 512
- Heartbeat interval SHALL be accepted only if in [5, 300]
- HTTP timeout SHALL be accepted only if in [1, 60]
- Max retries SHALL be accepted only if in [0, 10]
- Timeframe SHALL be accepted only if one of M1, M5, M15, H1
- Read timeout SHALL be accepted only if in [1, 60]

Any value outside its valid domain SHALL cause validation to fail.

Feature: ea-gateway, Property 14: Configuration Parameter Validation
"""

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from tests.mirror.config_manager import ConfigManager


# --------------------------------------------------------------------------
# Strategies (Smart generators)
# --------------------------------------------------------------------------

# URL strategies
valid_protocols = st.sampled_from(["http://", "https://", "HTTP://", "HTTPS://", "Http://", "hTtPs://"])
valid_hosts = st.from_regex(r"[a-z][a-z0-9\-\.]{0,50}\.[a-z]{2,6}", fullmatch=True)
valid_paths = st.from_regex(r"(/[a-z0-9\-_]{1,20}){0,5}", fullmatch=True)

# Build valid URLs from protocol + host + optional path
valid_urls = st.builds(
    lambda proto, host, path: proto + host + path,
    valid_protocols,
    valid_hosts,
    valid_paths,
).filter(lambda u: len(u) <= 2048)

# Invalid URL strategies: various ways URLs can be malformed
invalid_url_no_protocol = st.from_regex(r"[a-z][a-z0-9\.\-]{2,30}\.[a-z]{2,4}", fullmatch=True)
invalid_url_wrong_protocol = st.builds(
    lambda proto, host: proto + host,
    st.sampled_from(["ftp://", "ws://", "wss://", "file://", "tcp://", "mailto:", ""]),
    valid_hosts,
)
# URL that is just the protocol with no host
invalid_url_no_host = st.sampled_from(["http://", "https://", "HTTP://", "HTTPS://"])

# Token strategies
valid_tokens = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=512,
)
empty_tokens = st.just("")

# Numeric range strategies
valid_heartbeat = st.integers(min_value=5, max_value=300)
invalid_heartbeat_low = st.integers(min_value=-1000, max_value=4)
invalid_heartbeat_high = st.integers(min_value=301, max_value=10000)

valid_http_timeout = st.integers(min_value=1, max_value=60)
invalid_http_timeout_low = st.integers(min_value=-1000, max_value=0)
invalid_http_timeout_high = st.integers(min_value=61, max_value=10000)

valid_max_retries = st.integers(min_value=0, max_value=10)
invalid_max_retries_low = st.integers(min_value=-1000, max_value=-1)
invalid_max_retries_high = st.integers(min_value=11, max_value=10000)

valid_timeframes = st.sampled_from(["M1", "M5", "M15", "H1"])
invalid_timeframes = st.text(min_size=1, max_size=10).filter(
    lambda x: x not in ("M1", "M5", "M15", "H1")
)

valid_read_timeout = st.integers(min_value=1, max_value=60)
invalid_read_timeout_low = st.integers(min_value=-1000, max_value=0)
invalid_read_timeout_high = st.integers(min_value=61, max_value=10000)


# --------------------------------------------------------------------------
# Defaults for non-tested params (all valid)
# --------------------------------------------------------------------------
DEFAULTS = {
    "backend_url": "https://api.example.com",
    "auth_token": "valid-token-123",
    "heartbeat_sec": 30,
    "http_timeout_sec": 5,
    "max_retries": 3,
    "timeframe": "M1",
    "read_timeout_sec": 10,
}


# --------------------------------------------------------------------------
# Property Tests: URL Validation
# --------------------------------------------------------------------------

class TestUrlValidation:
    """Property tests for Backend URL validation."""

    @pytest.mark.property
    @given(url=valid_urls)
    def test_valid_url_accepted(self, url):
        """
        **Validates: Requirements 8.1**

        For any well-formed HTTP/HTTPS URL with length <= 2048,
        URL validation SHALL accept the value.
        """
        mgr = ConfigManager()
        result = mgr.validate_url(url)
        assert result is True, f"Valid URL rejected: '{url}', error: {mgr.validation_error}"

    @pytest.mark.property
    @given(url=invalid_url_no_protocol)
    def test_url_without_protocol_rejected(self, url):
        """
        **Validates: Requirements 8.1, 8.7**

        For any URL missing http:// or https:// prefix,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_url(url)
        assert result is False

    @pytest.mark.property
    @given(url=invalid_url_wrong_protocol)
    def test_url_with_wrong_protocol_rejected(self, url):
        """
        **Validates: Requirements 8.1, 8.7**

        For any URL with a non-HTTP(S) protocol (ftp, ws, file, etc.),
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_url(url)
        assert result is False

    @pytest.mark.property
    @given(url=invalid_url_no_host)
    def test_url_with_no_host_rejected(self, url):
        """
        **Validates: Requirements 8.1, 8.7**

        For any URL that is only the protocol (http:// or https://) with no host,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_url(url)
        assert result is False

    @pytest.mark.property
    @given(
        proto=st.sampled_from(["http://", "https://"]),
        host=valid_hosts,
        padding=st.text(min_size=2040, max_size=2100),
    )
    def test_url_exceeding_2048_chars_rejected(self, proto, host, padding):
        """
        **Validates: Requirements 8.1**

        For any URL exceeding 2048 characters in length,
        validation SHALL fail regardless of format correctness.
        """
        url = proto + host + "/" + padding
        assume(len(url) > 2048)
        mgr = ConfigManager()
        result = mgr.validate_url(url)
        assert result is False

    @pytest.mark.property
    def test_empty_url_rejected(self):
        """
        **Validates: Requirements 8.6**

        An empty/missing URL SHALL cause validation to fail.
        """
        mgr = ConfigManager()
        assert mgr.validate_url("") is False
        assert "missing" in mgr.validation_error.lower()


# --------------------------------------------------------------------------
# Property Tests: Auth Token Validation
# --------------------------------------------------------------------------

class TestAuthTokenValidation:
    """Property tests for auth token validation."""

    @pytest.mark.property
    @given(token=valid_tokens)
    def test_valid_token_accepted(self, token):
        """
        **Validates: Requirements 8.2**

        For any non-empty token with length <= 512,
        validation SHALL accept the value.
        """
        mgr = ConfigManager()
        result = mgr.validate_auth_token(token)
        assert result is True, f"Valid token rejected: len={len(token)}, error: {mgr.validation_error}"

    @pytest.mark.property
    @given(
        token=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
            min_size=513,
            max_size=1000,
        )
    )
    def test_token_exceeding_512_chars_rejected(self, token):
        """
        **Validates: Requirements 8.2**

        For any token exceeding 512 characters,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_auth_token(token)
        assert result is False

    @pytest.mark.property
    def test_empty_token_rejected(self):
        """
        **Validates: Requirements 8.6**

        An empty/missing auth token SHALL cause validation to fail.
        """
        mgr = ConfigManager()
        assert mgr.validate_auth_token("") is False
        assert "missing" in mgr.validation_error.lower()


# --------------------------------------------------------------------------
# Property Tests: Heartbeat Interval Validation
# --------------------------------------------------------------------------

class TestHeartbeatIntervalValidation:
    """Property tests for heartbeat interval validation."""

    @pytest.mark.property
    @given(value=valid_heartbeat)
    def test_valid_heartbeat_accepted(self, value):
        """
        **Validates: Requirements 8.3**

        For any heartbeat interval in [5, 300],
        validation SHALL accept the value.
        """
        mgr = ConfigManager()
        result = mgr.validate_heartbeat_interval(value)
        assert result is True

    @pytest.mark.property
    @given(value=invalid_heartbeat_low)
    def test_heartbeat_below_range_rejected(self, value):
        """
        **Validates: Requirements 8.3, 8.7**

        For any heartbeat interval below 5,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_heartbeat_interval(value)
        assert result is False

    @pytest.mark.property
    @given(value=invalid_heartbeat_high)
    def test_heartbeat_above_range_rejected(self, value):
        """
        **Validates: Requirements 8.3, 8.7**

        For any heartbeat interval above 300,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_heartbeat_interval(value)
        assert result is False


# --------------------------------------------------------------------------
# Property Tests: HTTP Timeout Validation
# --------------------------------------------------------------------------

class TestHttpTimeoutValidation:
    """Property tests for HTTP timeout validation."""

    @pytest.mark.property
    @given(value=valid_http_timeout)
    def test_valid_http_timeout_accepted(self, value):
        """
        **Validates: Requirements 8.4**

        For any HTTP timeout in [1, 60],
        validation SHALL accept the value.
        """
        mgr = ConfigManager()
        result = mgr.validate_http_timeout(value)
        assert result is True

    @pytest.mark.property
    @given(value=invalid_http_timeout_low)
    def test_http_timeout_below_range_rejected(self, value):
        """
        **Validates: Requirements 8.4, 8.7**

        For any HTTP timeout below 1,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_http_timeout(value)
        assert result is False

    @pytest.mark.property
    @given(value=invalid_http_timeout_high)
    def test_http_timeout_above_range_rejected(self, value):
        """
        **Validates: Requirements 8.4, 8.7**

        For any HTTP timeout above 60,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_http_timeout(value)
        assert result is False


# --------------------------------------------------------------------------
# Property Tests: Max Retries Validation
# --------------------------------------------------------------------------

class TestMaxRetriesValidation:
    """Property tests for max retries validation."""

    @pytest.mark.property
    @given(value=valid_max_retries)
    def test_valid_max_retries_accepted(self, value):
        """
        **Validates: Requirements 8.5**

        For any max retries in [0, 10],
        validation SHALL accept the value.
        """
        mgr = ConfigManager()
        result = mgr.validate_max_retries(value)
        assert result is True

    @pytest.mark.property
    @given(value=invalid_max_retries_low)
    def test_max_retries_below_range_rejected(self, value):
        """
        **Validates: Requirements 8.5, 8.7**

        For any max retries below 0,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_max_retries(value)
        assert result is False

    @pytest.mark.property
    @given(value=invalid_max_retries_high)
    def test_max_retries_above_range_rejected(self, value):
        """
        **Validates: Requirements 8.5, 8.7**

        For any max retries above 10,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_max_retries(value)
        assert result is False


# --------------------------------------------------------------------------
# Property Tests: Timeframe Validation
# --------------------------------------------------------------------------

class TestTimeframeValidation:
    """Property tests for timeframe validation."""

    @pytest.mark.property
    @given(tf=valid_timeframes)
    def test_valid_timeframe_accepted(self, tf):
        """
        **Validates: Requirements 8.7**

        For any timeframe in {M1, M5, M15, H1},
        validation SHALL accept the value.
        """
        mgr = ConfigManager()
        result = mgr.validate_timeframe(tf)
        assert result is True

    @pytest.mark.property
    @given(tf=invalid_timeframes)
    def test_invalid_timeframe_rejected(self, tf):
        """
        **Validates: Requirements 8.7**

        For any timeframe not in {M1, M5, M15, H1},
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_timeframe(tf)
        assert result is False


# --------------------------------------------------------------------------
# Property Tests: Read Timeout Validation
# --------------------------------------------------------------------------

class TestReadTimeoutValidation:
    """Property tests for read timeout validation."""

    @pytest.mark.property
    @given(value=valid_read_timeout)
    def test_valid_read_timeout_accepted(self, value):
        """
        **Validates: Requirements 8.7**

        For any read timeout in [1, 60],
        validation SHALL accept the value.
        """
        mgr = ConfigManager()
        result = mgr.validate_read_timeout(value)
        assert result is True

    @pytest.mark.property
    @given(value=invalid_read_timeout_low)
    def test_read_timeout_below_range_rejected(self, value):
        """
        **Validates: Requirements 8.7**

        For any read timeout below 1,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_read_timeout(value)
        assert result is False

    @pytest.mark.property
    @given(value=invalid_read_timeout_high)
    def test_read_timeout_above_range_rejected(self, value):
        """
        **Validates: Requirements 8.7**

        For any read timeout above 60,
        validation SHALL fail.
        """
        mgr = ConfigManager()
        result = mgr.validate_read_timeout(value)
        assert result is False


# --------------------------------------------------------------------------
# Property Tests: Full Configuration Validation (end-to-end)
# --------------------------------------------------------------------------

class TestFullConfigValidation:
    """Property tests for the complete load_and_validate flow."""

    @pytest.mark.property
    @given(
        url=valid_urls,
        token=valid_tokens,
        heartbeat=valid_heartbeat,
        http_timeout=valid_http_timeout,
        max_retries=valid_max_retries,
        timeframe=valid_timeframes,
        read_timeout=valid_read_timeout,
    )
    def test_all_valid_params_pass(
        self, url, token, heartbeat, http_timeout, max_retries, timeframe, read_timeout
    ):
        """
        **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.7**

        For any set of configuration parameters where all are within valid domains,
        load_and_validate SHALL return True.
        """
        mgr = ConfigManager()
        result = mgr.load_and_validate(
            backend_url=url,
            auth_token=token,
            heartbeat_sec=heartbeat,
            http_timeout_sec=http_timeout,
            max_retries=max_retries,
            timeframe=timeframe,
            read_timeout_sec=read_timeout,
        )
        assert result is True, f"Valid config rejected: {mgr.validation_error}"

    @pytest.mark.property
    @given(
        token=valid_tokens,
        heartbeat=valid_heartbeat,
        http_timeout=valid_http_timeout,
        max_retries=valid_max_retries,
        timeframe=valid_timeframes,
        read_timeout=valid_read_timeout,
    )
    def test_invalid_url_fails_full_validation(
        self, token, heartbeat, http_timeout, max_retries, timeframe, read_timeout
    ):
        """
        **Validates: Requirements 8.6, 8.7**

        If the backend URL is invalid (empty), the full validation SHALL fail
        even if all other parameters are valid.
        """
        mgr = ConfigManager()
        result = mgr.load_and_validate(
            backend_url="",
            auth_token=token,
            heartbeat_sec=heartbeat,
            http_timeout_sec=http_timeout,
            max_retries=max_retries,
            timeframe=timeframe,
            read_timeout_sec=read_timeout,
        )
        assert result is False
        assert "BackendUrl" in mgr.validation_error

    @pytest.mark.property
    @given(
        url=valid_urls,
        heartbeat=valid_heartbeat,
        http_timeout=valid_http_timeout,
        max_retries=valid_max_retries,
        timeframe=valid_timeframes,
        read_timeout=valid_read_timeout,
    )
    def test_empty_token_fails_full_validation(
        self, url, heartbeat, http_timeout, max_retries, timeframe, read_timeout
    ):
        """
        **Validates: Requirements 8.6**

        If the auth token is empty, the full validation SHALL fail
        even if all other parameters are valid.
        """
        mgr = ConfigManager()
        result = mgr.load_and_validate(
            backend_url=url,
            auth_token="",
            heartbeat_sec=heartbeat,
            http_timeout_sec=http_timeout,
            max_retries=max_retries,
            timeframe=timeframe,
            read_timeout_sec=read_timeout,
        )
        assert result is False
        assert "AuthToken" in mgr.validation_error
