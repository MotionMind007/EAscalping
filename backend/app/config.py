"""Application configuration via pydantic-settings.

All parameters are loaded from environment variables (or .env file).
Required values (database_url, redis_url, auth_token) must be set or startup will fail.
Numeric values are validated with Field constraints for reasonable bounds.
"""
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Backend Gateway configuration.

    Required environment variables:
        DATABASE_URL - PostgreSQL async connection string
        REDIS_URL - Redis connection string
        AUTH_TOKEN - Bearer token for EA authentication
    """

    # Infrastructure (required - no defaults)
    database_url: str = Field(..., description="PostgreSQL async connection string")
    redis_url: str = Field(..., description="Redis connection string")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    auth_token: str = Field(..., description="Bearer token for EA authentication")

    # Trading parameters
    lot_size: float = Field(default=0.10, ge=0.01, le=10.0, description="Trade lot size")
    stop_loss_points: int = Field(default=100, ge=10, le=1000, description="Stop loss in points")
    take_profit_points: int = Field(default=150, ge=10, le=1000, description="Take profit in points")
    max_daily_loss_pct: float = Field(default=3.0, ge=0.1, le=100.0, description="Max daily loss percentage")

    # Trading instrument
    symbol: str = Field(default="XAUUSD", description="Trading symbol")
    timeframe: str = Field(default="M5", description="Chart timeframe for candle data")

    # Indicator parameters
    ema_fast_period: int = Field(default=9, ge=2, le=200, description="EMA fast period")
    ema_slow_period: int = Field(default=21, ge=2, le=200, description="EMA slow period")
    rsi_period: int = Field(default=14, ge=2, le=200, description="RSI period")
    rsi_overbought: int = Field(default=70, ge=50, le=99, description="RSI overbought threshold")
    rsi_oversold: int = Field(default=30, ge=1, le=50, description="RSI oversold threshold")
    max_spread_points: int = Field(default=40, ge=1, le=200, description="Max spread in points")

    # Session times (UTC hours)
    london_start_hour: int = Field(default=8, ge=0, le=23, description="London session start (UTC)")
    london_end_hour: int = Field(default=16, ge=0, le=23, description="London session end (UTC)")
    ny_start_hour: int = Field(default=13, ge=0, le=23, description="New York session start (UTC)")
    ny_end_hour: int = Field(default=21, ge=0, le=23, description="New York session end (UTC)")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
