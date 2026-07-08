"""Dependency injection for FastAPI.

Provides:
- Redis client wrapper with connection pool management
- SQLAlchemy async session factory
- Auth token verification (Bearer token from X-Auth-Token or Authorization header)

Global instances are initialized during the application lifespan (see main.py).
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

# ─── Global instances (initialized in lifespan) ─────────────────────────────

redis_client: Optional[Redis] = None
async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


# ─── Redis Client Wrapper ────────────────────────────────────────────────────


class RedisClient:
    """Redis client wrapper with connection pool management.

    Provides automatic connection pooling, error handling, and
    async context manager support for clean resource management.
    """

    def __init__(self, url: str, max_connections: int = 10):
        """Initialize Redis client with connection pool.

        Args:
            url: Redis connection URL (e.g., redis://localhost:6379/0)
            max_connections: Maximum number of connections in the pool
        """
        self._pool = ConnectionPool.from_url(
            url,
            max_connections=max_connections,
            decode_responses=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self._url = url

    async def connect(self) -> None:
        """Establish connection pool (called during startup)."""
        # Connection pool is lazy, connections are created on demand
        pass

    async def disconnect(self) -> None:
        """Close all connections in the pool (called during shutdown)."""
        await self._pool.disconnect()

    async def __aenter__(self) -> Redis:
        """Async context manager entry - returns Redis instance."""
        return Redis(connection_pool=self._pool)

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup."""
        pass

    def get_redis(self) -> Redis:
        """Get a Redis instance from the pool."""
        return Redis(connection_pool=self._pool)

    @property
    def url(self) -> str:
        """Return the Redis URL."""
        return self._url


# ─── Global Redis instance (initialized in lifespan) ─────────────────────────

_redis_wrapper: Optional[RedisClient] = None


# ─── Settings singleton ──────────────────────────────────────────────────────


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance loaded from environment."""
    return Settings()


# ─── Dependencies ────────────────────────────────────────────────────────────


async def get_redis() -> Redis:
    """Provide the Redis client to route handlers.

    Returns a Redis instance from the connection pool.
    Raises HTTP 503 if Redis is not initialized.
    """
    if _redis_wrapper is None:
        raise HTTPException(status_code=503, detail="Redis not initialized")
    return _redis_wrapper.get_redis()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a SQLAlchemy async session, auto-committed on success.

    Yields:
        AsyncSession: SQLAlchemy async database session

    Raises:
        HTTPException: If database is not initialized (503)
    """
    if async_session_factory is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def verify_auth_token(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    authorization: Optional[str] = Header(None),
) -> str:
    """Validate Bearer token from X-Auth-Token or Authorization header.

    Accepts token in either:
    - X-Auth-Token header (plain token)
    - Authorization header (Bearer <token>)

    Args:
        x_auth_token: Token from X-Auth-Token header
        authorization: Token from Authorization header (Bearer scheme)

    Returns:
        The validated token string

    Raises:
        HTTPException: If token is missing or invalid (401)
    """
    settings = get_settings()
    token = None

    # Check X-Auth-Token header first
    if x_auth_token:
        token = x_auth_token
    # Check Authorization header for Bearer token
    elif authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token or token != settings.auth_token:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")


# ─── Lifespan helpers for Redis initialization ───────────────────────────────


@asynccontextmanager
async def redis_lifespan(app: FastAPI):
    """Lifespan context manager for Redis initialization.

    Creates Redis connection pool on startup and closes on shutdown.
    """
    settings = get_settings()
    global _redis_wrapper

    _redis_wrapper = RedisClient(
        url=settings.redis_url,
        max_connections=10,
    )
    await _redis_wrapper.connect()
    global redis_client
    redis_client = _redis_wrapper.get_redis()

    yield

    if _redis_wrapper:
        await _redis_wrapper.disconnect()
        _redis_wrapper = None
    redis_client = None
