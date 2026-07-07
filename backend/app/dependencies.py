"""Dependency injection for FastAPI.

Provides:
- Redis client (async connection pool)
- SQLAlchemy async session factory
- Auth token verification (header-based)

Global instances are initialized during the application lifespan (see main.py).
"""
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

# ─── Global instances (initialized in lifespan) ─────────────────────────────

redis_client: Optional[Redis] = None
async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


# ─── Settings singleton ──────────────────────────────────────────────────────


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance loaded from environment."""
    return Settings()


# ─── Dependencies ────────────────────────────────────────────────────────────


async def get_redis() -> Redis:
    """Provide the Redis client to route handlers."""
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis not initialized")
    return redis_client


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a SQLAlchemy async session, auto-committed on success."""
    if async_session_factory is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def verify_auth_token(x_auth_token: str = Header(None)) -> None:
    """Validate the X-Auth-Token header against the configured secret.

    Raises HTTP 401 if the token is missing or doesn't match.
    """
    settings = get_settings()
    if not x_auth_token or x_auth_token != settings.auth_token:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")
