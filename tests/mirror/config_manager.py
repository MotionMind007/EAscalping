"""
Python mirror implementation of CConfigManager (Include/EAGateway/ConfigManager.mqh).

This module provides the same validation logic as the MQL5 implementation
for property-based testing.

It mirrors:
  - URL validation: well-formed HTTP/HTTPS, max 2048 chars, must have host after protocol
  - Auth token validation: non-empty, max 512 chars
  - Heartbeat interval validation: range [5, 300]
  - HTTP timeout validation: range [1, 60]
  - Max retries validation: range [0, 10]
  - Timeframe validation: one of M1, M5, M15, H1
  - Read timeout validation: range [1, 60]

Feature: ea-gateway
"""

from dataclasses import dataclass
from typing import Tuple


# --------------------------------------------------------------------------
# Configuration data structure
# --------------------------------------------------------------------------

@dataclass
class EAConfig:
    """Mirrors the CConfigManager stored configuration."""
    backend_url: str = ""
    auth_token: str = ""
    heartbeat_interval: int = 30
    http_timeout: int = 5
    max_retries: int = 3
    timeframe: str = "M1"
    read_timeout: int = 10


# --------------------------------------------------------------------------
# ConfigManager mirror
# --------------------------------------------------------------------------

class ConfigManager:
    """
    Python mirror of CConfigManager.

    Validates all configurable input parameters at startup.
    If any validation fails, the EA remains in BOOT state.
    """

    VALID_TIMEFRAMES = ("M1", "M5", "M15", "H1")

    def __init__(self):
        self._validation_error: str = ""
        self._config: EAConfig = EAConfig()

    @property
    def validation_error(self) -> str:
        return self._validation_error

    @property
    def config(self) -> EAConfig:
        return self._config

    def load_and_validate(
        self,
        backend_url: str,
        auth_token: str,
        heartbeat_sec: int,
        http_timeout_sec: int,
        max_retries: int,
        timeframe: str,
        read_timeout_sec: int,
    ) -> bool:
        """
        Validate all parameters. Returns True if all pass, False otherwise.
        On failure, validation_error contains the reason.
        """
        self._validation_error = ""

        if not self.validate_url(backend_url):
            return False

        if not self.validate_auth_token(auth_token):
            return False

        if not self.validate_heartbeat_interval(heartbeat_sec):
            return False

        if not self.validate_http_timeout(http_timeout_sec):
            return False

        if not self.validate_max_retries(max_retries):
            return False

        if not self.validate_timeframe(timeframe):
            return False

        if not self.validate_read_timeout(read_timeout_sec):
            return False

        # All passed - store values
        self._config = EAConfig(
            backend_url=backend_url,
            auth_token=auth_token,
            heartbeat_interval=heartbeat_sec,
            http_timeout=http_timeout_sec,
            max_retries=max_retries,
            timeframe=timeframe,
            read_timeout=read_timeout_sec,
        )
        return True

    def validate_url(self, url: str) -> bool:
        """
        Validate Backend URL (Req 8.1, 8.6).

        Rules:
        - Must not be empty/None
        - Max 2048 characters
        - Must start with http:// or https:// (case-insensitive)
        - Must have content (host) after the protocol prefix
        """
        # Check for missing/empty URL
        if url is None or len(url) == 0:
            self._validation_error = "BackendUrl: required parameter is missing"
            return False

        # Check max length
        if len(url) > 2048:
            self._validation_error = "BackendUrl: exceeds maximum length of 2048 characters"
            return False

        # Check well-formed: must start with http:// or https://
        url_lower = url.lower()

        if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
            self._validation_error = "BackendUrl: must start with http:// or https://"
            return False

        # Check that there is content after the protocol prefix
        if url_lower.startswith("https://"):
            protocol_len = 8  # len("https://")
        else:
            protocol_len = 7  # len("http://")

        if len(url) <= protocol_len:
            self._validation_error = "BackendUrl: URL has no host after protocol"
            return False

        return True

    def validate_auth_token(self, token: str) -> bool:
        """
        Validate auth token (Req 8.2, 8.6).

        Rules:
        - Must not be empty/None
        - Max 512 characters
        """
        if token is None or len(token) == 0:
            self._validation_error = "AuthToken: required parameter is missing"
            return False

        if len(token) > 512:
            self._validation_error = "AuthToken: exceeds maximum length of 512 characters"
            return False

        return True

    def validate_heartbeat_interval(self, value: int) -> bool:
        """
        Validate heartbeat interval (Req 8.3).

        Rules: range [5, 300]
        """
        if value < 5 or value > 300:
            self._validation_error = (
                f"HeartbeatInterval: value {value} is outside valid range [5, 300]"
            )
            return False
        return True

    def validate_http_timeout(self, value: int) -> bool:
        """
        Validate HTTP timeout (Req 8.4).

        Rules: range [1, 60]
        """
        if value < 1 or value > 60:
            self._validation_error = (
                f"HttpTimeout: value {value} is outside valid range [1, 60]"
            )
            return False
        return True

    def validate_max_retries(self, value: int) -> bool:
        """
        Validate max retries (Req 8.5).

        Rules: range [0, 10]
        """
        if value < 0 or value > 10:
            self._validation_error = (
                f"MaxRetries: value {value} is outside valid range [0, 10]"
            )
            return False
        return True

    def validate_timeframe(self, tf: str) -> bool:
        """
        Validate timeframe (Req 8.7).

        Rules: must be one of M1, M5, M15, H1
        """
        if tf not in self.VALID_TIMEFRAMES:
            self._validation_error = (
                f"Timeframe: value '{tf}' is not valid (must be M1, M5, M15, or H1)"
            )
            return False
        return True

    def validate_read_timeout(self, value: int) -> bool:
        """
        Validate read timeout (Req 8.7).

        Rules: range [1, 60]
        """
        if value < 1 or value > 60:
            self._validation_error = (
                f"ReadTimeout: value {value} is outside valid range [1, 60]"
            )
            return False
        return True
