"""Market data router — tick and candle ingestion endpoints.

Receives real-time market data from the EA and stores it in Redis
for fast access by the Signal Engine and other services.
"""
import json
import logging

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis, verify_auth_token
from app.db.repository import Repository
from app.models.requests import CandlePayload, TickPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.post("/tick", dependencies=[Depends(verify_auth_token)])
async def receive_tick(
    payload: TickPayload,
    redis: Redis = Depends(get_redis),
) -> dict:
    """Store tick data in Redis.

    Stores the latest tick for the symbol at key `market:tick:{symbol}`.
    The value is a JSON-encoded string of the most recent tick in the array.
    """
    # Store latest tick (last in the array) for the symbol
    latest_tick = payload.ticks[-1]
    tick_data = json.dumps({
        "symbol": payload.symbol,
        "timestamp": str(latest_tick.timestamp),
        "bid": latest_tick.bid,
        "ask": latest_tick.ask,
        "spread": latest_tick.spread,
    })
    await redis.set(
        f"market:tick:{payload.symbol}",
        tick_data,
        ex=60,  # 60-second TTL
    )
    logger.debug("Stored tick for %s: bid=%.5f ask=%.5f", payload.symbol, latest_tick.bid, latest_tick.ask)
    return {}


@router.post("/candle", dependencies=[Depends(verify_auth_token)])
async def receive_candle(
    payload: CandlePayload,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Store candle data in Redis candle buffer and PostgreSQL.

    Appends candle to Redis list `market:candles:{symbol}:{timeframe}` and
    trims to keep only the latest 100 candles (rolling buffer).
    Also inserts into PostgreSQL candles table for persistent storage.
    """
    candle_data = json.dumps({
        "symbol": payload.symbol,
        "timeframe": payload.timeframe,
        "timestamp": str(payload.timestamp),
        "open": payload.open,
        "high": payload.high,
        "low": payload.low,
        "close": payload.close,
        "volume": payload.volume,
    })
    key = f"market:candles:{payload.symbol}:{payload.timeframe}"
    await redis.rpush(key, candle_data)
    await redis.ltrim(key, -100, -1)  # Keep last 100 candles
    
    # Insert into PostgreSQL for persistent storage
    repo = Repository(db)
    from app.db.models import Candle
    from datetime import datetime
    
    candle_record = Candle(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        timestamp=datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00")),
        open=payload.open,
        high=payload.high,
        low=payload.low,
        close=payload.close,
        volume=payload.volume,
    )
    db.add(candle_record)
    await db.flush()
    
    logger.debug("Stored candle for %s %s at %s", payload.symbol, payload.timeframe, payload.timestamp)
    return {}
