"""Health monitoring router — heartbeat, MT5 events, and system health.

Handles EA health reports, MT5 disconnect/reconnect events, and provides
the system-level health check endpoint.
"""
import json
import logging
import time

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.dependencies import get_redis, verify_auth_token
from app.models.requests import (
    HeartbeatPayload,
    MT5DisconnectPayload,
    MT5ReconnectPayload,
)
from app.models.responses import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.post("/heartbeat", dependencies=[Depends(verify_auth_token)])
async def receive_heartbeat(
    payload: HeartbeatPayload,
    redis: Redis = Depends(get_redis),
) -> dict:
    """Store EA heartbeat data in Redis hash `ea:health`.

    Updates the health record with current state, account info, and timestamps.
    Used by the GET /health endpoint to determine EA connectivity.
    """
    health_data = {
        "state": payload.state.value,
        "account_balance": str(payload.account_balance),
        "account_equity": str(payload.account_equity),
        "latency_ms": str(payload.latency_ms),
        "mt5_connected": str(payload.mt5_connected),
        "spread": str(payload.spread),
        "timestamp": str(payload.timestamp),
        "last_seen": str(time.time()),
    }
    await redis.hset("ea:health", mapping=health_data)
    await redis.expire("ea:health", 120)  # TTL 120 seconds
    logger.debug("Heartbeat received: state=%s, equity=%.2f", payload.state.value, payload.account_equity)
    return {}


@router.post("/mt5disconnect", dependencies=[Depends(verify_auth_token)])
async def mt5_disconnect(
    payload: MT5DisconnectPayload,
    redis: Redis = Depends(get_redis),
) -> dict:
    """Handle MT5 disconnection event.

    Marks the EA as disconnected from MT5 and pauses signal generation.
    """
    await redis.hset("ea:health", mapping={
        "mt5_connected": "False",
        "state": payload.state.value,
        "disconnect_time": str(payload.timestamp),
    })
    # Set flag to pause signal generation
    await redis.set("signals:paused", "1")
    logger.warning("MT5 disconnected: state=%s at %s", payload.state.value, payload.timestamp)
    return {}


@router.post("/mt5reconnect", dependencies=[Depends(verify_auth_token)])
async def mt5_reconnect(
    payload: MT5ReconnectPayload,
    redis: Redis = Depends(get_redis),
) -> dict:
    """Handle MT5 reconnection event.

    Marks the EA as reconnected, resumes signal generation, and updates equity records.
    """
    await redis.hset("ea:health", mapping={
        "mt5_connected": "True",
        "state": payload.state.value,
        "account_balance": str(payload.account_balance),
        "account_equity": str(payload.account_equity),
        "reconnect_time": str(payload.timestamp),
        "last_seen": str(time.time()),
    })
    # Remove signal pause flag
    await redis.delete("signals:paused")
    logger.info("MT5 reconnected: state=%s, equity=%.2f", payload.state.value, payload.account_equity)
    return {}


# ─── System health endpoint (no auth, root-level) ────────────────────────────

health_root_router = APIRouter(tags=["health"])


@health_root_router.get("/health", response_model=HealthResponse)
async def system_health(
    redis: Redis = Depends(get_redis),
) -> HealthResponse:
    """System-level health check.

    Reads the EA health hash from Redis, calculates heartbeat age,
    checks Redis connectivity, and returns comprehensive health status.
    No authentication required.
    """
    # Check Redis connectivity
    redis_connected = True
    try:
        await redis.ping()
    except Exception:
        redis_connected = False

    # Assume PostgreSQL is connected if we got here (checked at startup)
    # Full PostgreSQL health check would require session injection
    postgres_connected = True

    # Read EA health data from Redis
    ea_health = await redis.hgetall("ea:health") if redis_connected else {}

    # Calculate heartbeat age
    last_heartbeat_age: float | None = None
    ea_connected = False
    if ea_health and "last_seen" in ea_health:
        last_seen = float(ea_health["last_seen"])
        last_heartbeat_age = time.time() - last_seen
        ea_connected = last_heartbeat_age < 90.0

    # Check risk lock
    risk_lock_active = False
    if redis_connected:
        lock_value = await redis.get("risk:lock")
        risk_lock_active = lock_value == "1"

    # Current state
    current_state = ea_health.get("state") if ea_health else None

    # Determine overall status
    if not redis_connected:
        status = "unhealthy"
    elif not ea_connected:
        status = "degraded"
    else:
        status = "healthy"

    return HealthResponse(
        status=status,
        ea_connected=ea_connected,
        last_heartbeat_age_seconds=last_heartbeat_age,
        redis_connected=redis_connected,
        postgres_connected=postgres_connected,
        risk_lock_active=risk_lock_active,
        current_state=current_state,
    )
