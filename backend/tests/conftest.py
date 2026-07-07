"""Shared test fixtures for the backend gateway tests."""
import pytest
import pytest_asyncio


@pytest.fixture
def settings():
    """Provide test settings with required env vars set."""
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("AUTH_TOKEN", "test-token-secret")
    from app.config import Settings
    return Settings()
