"""
Python mirror implementation of CHttpClient response dispatch logic
(Include/EAGateway/HttpClient.mqh).

This module mirrors the HTTP response categorization, retry/discard decisions,
and JSON validation logic for property-based testing.

Feature: ea-gateway
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------
# Constants matching HttpClient.mqh
# --------------------------------------------------------------------------

HTTP_BACKOFF_BASE_MS = 1000  # Base backoff: 1 second
DEFAULT_MAX_RETRIES = 3


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class ResponseAction(Enum):
    """Action taken by the HttpClient upon receiving a response."""
    PARSE_JSON = "PARSE_JSON"       # 2xx with valid JSON
    DISCARD_NO_RETRY = "DISCARD"    # 4xx, or invalid JSON regardless of status
    RETRY_WITH_BACKOFF = "RETRY"    # 5xx (if retries remain)
    EXHAUSTED = "EXHAUSTED"         # 5xx after all retries used


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class HttpResponse:
    """Mirrors the MQL5 HttpResponse struct."""
    status_code: int = 0
    body: str = ""
    latency_ms: int = 0
    is_valid: bool = False


@dataclass
class DispatchDecision:
    """Result of dispatching an HTTP response."""
    action: ResponseAction = ResponseAction.DISCARD_NO_RETRY
    should_retry: bool = False
    backoff_ms: int = 0
    parsed_body: Optional[dict] = None


# --------------------------------------------------------------------------
# HTTP Client Response Dispatch (mirror of CHttpClient logic)
# --------------------------------------------------------------------------

class HttpClientDispatch:
    """
    Python mirror of CHttpClient response dispatch logic.

    Implements:
    - Status code categorization (2xx, 4xx, 5xx)
    - JSON validation
    - Retry decision with exponential backoff
    - Discard decisions
    """

    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES):
        self.max_retries = max_retries

    def is_valid_json(self, body: str) -> bool:
        """
        Check if body is valid JSON.

        Mirrors CHttpClient::IsValidJson - basic heuristic check that
        the body starts with '{' or '[' and can be parsed.
        """
        if not body or not body.strip():
            return False

        trimmed = body.strip()
        first_char = trimmed[0]

        if first_char not in ("{", "["):
            return False

        # Attempt actual JSON parse for full validation
        try:
            json.loads(trimmed)
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    def should_retry(self, status_code: int, attempt: int) -> bool:
        """
        Determine if request should be retried.

        Only 5xx responses are retried, up to max_retries times.
        Mirrors CHttpClient::ShouldRetry.
        """
        if 500 <= status_code < 600:
            return attempt < self.max_retries
        return False

    def get_backoff_ms(self, attempt: int) -> int:
        """
        Calculate exponential backoff delay.

        Pattern: 1000ms * 2^attempt
        attempt 0 → 1000ms, attempt 1 → 2000ms, attempt 2 → 4000ms
        Mirrors CHttpClient::GetBackoffMs.
        """
        return HTTP_BACKOFF_BASE_MS * (2 ** attempt)

    def dispatch_response(self, status_code: int, body: str, attempt: int = 0) -> DispatchDecision:
        """
        Determine the action to take for a given HTTP response.

        Logic (mirrors CHttpClient::Post):
        1. If body is not valid JSON → DISCARD (regardless of status code)
        2. If status is 2xx → PARSE_JSON (valid JSON already confirmed)
        3. If status is 4xx → DISCARD_NO_RETRY
        4. If status is 5xx and retries remain → RETRY_WITH_BACKOFF
        5. If status is 5xx and retries exhausted → EXHAUSTED (discard)

        Args:
            status_code: HTTP status code (200-599)
            body: Response body string
            attempt: Current retry attempt (0-based)

        Returns:
            DispatchDecision with the action and supporting data
        """
        decision = DispatchDecision()
        body_is_valid_json = self.is_valid_json(body)

        # Rule: Invalid JSON → discard without retry regardless of status
        if not body_is_valid_json:
            decision.action = ResponseAction.DISCARD_NO_RETRY
            decision.should_retry = False
            decision.backoff_ms = 0
            decision.parsed_body = None
            return decision

        # 2xx Success: parse JSON response
        if 200 <= status_code < 300:
            decision.action = ResponseAction.PARSE_JSON
            decision.should_retry = False
            decision.backoff_ms = 0
            try:
                decision.parsed_body = json.loads(body.strip())
            except (json.JSONDecodeError, ValueError):
                # Should not happen since is_valid_json passed, but handle gracefully
                decision.action = ResponseAction.DISCARD_NO_RETRY
                decision.parsed_body = None
            return decision

        # 4xx Client Error: discard without retry
        if 400 <= status_code < 500:
            decision.action = ResponseAction.DISCARD_NO_RETRY
            decision.should_retry = False
            decision.backoff_ms = 0
            decision.parsed_body = None
            return decision

        # 5xx Server Error: retry with backoff if retries remain
        if 500 <= status_code < 600:
            if self.should_retry(status_code, attempt):
                decision.action = ResponseAction.RETRY_WITH_BACKOFF
                decision.should_retry = True
                decision.backoff_ms = self.get_backoff_ms(attempt)
                decision.parsed_body = None
            else:
                decision.action = ResponseAction.EXHAUSTED
                decision.should_retry = False
                decision.backoff_ms = 0
                decision.parsed_body = None
            return decision

        # Unexpected status codes: discard
        decision.action = ResponseAction.DISCARD_NO_RETRY
        decision.should_retry = False
        decision.backoff_ms = 0
        decision.parsed_body = None
        return decision

    def build_headers(self, auth_token: str) -> dict:
        """
        Build HTTP headers with auth token.

        Mirrors CHttpClient::BuildHeaders.
        Every request includes Content-Type and X-Auth-Token.
        """
        return {
            "Content-Type": "application/json",
            "X-Auth-Token": auth_token,
        }
