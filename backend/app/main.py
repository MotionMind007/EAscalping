"""AI Scalping Backend Gateway - FastAPI application.

Initializes Redis and PostgreSQL connection pools during startup,
registers all API routers, and provides the /health endpoint.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import dependencies
from app.config import Settings
from app.dependencies import get_settings
from app.routers import health, market, position, state, trade
from app.routers.health import health_root_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle.

    Startup: create Redis client and SQLAlchemy async engine/session factory.
    Shutdown: close Redis connection and dispose engine pool.
    """
    settings: Settings = get_settings()

    # ─── Initialize Redis ─────────────────────────────────────────────────
    dependencies.redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    logger.info("Redis connection pool created: %s", settings.redis_url)

    # ─── Initialize PostgreSQL (SQLAlchemy async) ─────────────────────────
    engine = create_async_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    dependencies.async_session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    logger.info("PostgreSQL engine created: %s", settings.database_url.split("@")[-1])

    yield

    # ─── Shutdown ─────────────────────────────────────────────────────────
    if dependencies.redis_client:
        await dependencies.redis_client.close()
        logger.info("Redis connection closed")

    await engine.dispose()
    logger.info("PostgreSQL engine disposed")

    # Reset global references
    dependencies.redis_client = None
    dependencies.async_session_factory = None


app = FastAPI(
    title="AI Scalping Backend Gateway",
    version="1.0.0",
    description="Decision-making brain of the AI Scalping XAUUSD platform",
    lifespan=lifespan,
)

# Include routers
app.include_router(market.router)
app.include_router(health.router)
app.include_router(health_root_router)
app.include_router(state.router)
app.include_router(trade.router)
app.include_router(position.router)
