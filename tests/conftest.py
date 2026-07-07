"""
Shared fixtures and Hypothesis profiles for EA Gateway property-based tests.

Feature: ea-gateway
"""

import pytest
from hypothesis import settings, HealthCheck, Phase

# --------------------------------------------------------------------------
# Hypothesis Profiles
# --------------------------------------------------------------------------

# Default profile: minimum 100 examples per property test (as per design spec)
settings.register_profile(
    "default",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
)

# CI profile: more examples for thorough testing in CI pipelines
settings.register_profile(
    "ci",
    max_examples=500,
    suppress_health_check=[HealthCheck.too_slow],
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
)

# Debug profile: fewer examples for fast iteration during development
settings.register_profile(
    "debug",
    max_examples=10,
    suppress_health_check=[HealthCheck.too_slow],
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
)

# Load the default profile
settings.load_profile("default")


# --------------------------------------------------------------------------
# Shared Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def ea_states():
    """All valid EA states as defined in the state machine."""
    return [
        "BOOT",
        "CONNECT",
        "WAIT_SESSION",
        "CHECK_RISK",
        "SCAN_SIGNAL",
        "AI_CONFIRMATION",
        "OPEN_POSITION",
        "MANAGE_POSITION",
        "POSITION_CLOSED",
        "DISCONNECTED",
    ]


@pytest.fixture
def session_hours():
    """Session window boundaries (UTC)."""
    return {
        "london_start": 8,
        "london_end": 16,
        "ny_start": 13,
        "ny_end": 21,
    }


@pytest.fixture
def valid_config():
    """A valid EA configuration for testing."""
    return {
        "backend_url": "https://api.example.com",
        "auth_token": "test-token-abc123",
        "heartbeat_sec": 30,
        "http_timeout_sec": 5,
        "max_retries": 3,
        "timeframe": "M1",
        "read_timeout_sec": 10,
    }
