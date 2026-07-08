"""Property-based tests for Settings configuration validation.

Validates that Settings properly rejects invalid configurations
and accepts valid configurations.

Validates: Requirements 8.5, 8.6
"""
import pytest
import os
from hypothesis import given, strategies as st, settings as hypothesis_settings
from pydantic import ValidationError

# Required environment variable values (valid)
VALID_DB_URL = "postgresql+asyncpg://test:test@localhost:5432/test_db"
VALID_REDIS_URL = "redis://localhost:6379/0"
VALID_AUTH_TOKEN = "test-token-secret"


def set_valid_env():
    """Set valid environment variables."""
    os.environ['DATABASE_URL'] = VALID_DB_URL
    os.environ['REDIS_URL'] = VALID_REDIS_URL
    os.environ['AUTH_TOKEN'] = VALID_AUTH_TOKEN


def clear_env():
    """Clear all relevant environment variables."""
    vars_to_clear = [
        'DATABASE_URL', 'REDIS_URL', 'AUTH_TOKEN',
        'LOT_SIZE', 'STOP_LOSS_POINTS', 'TAKE_PROFIT_POINTS', 'MAX_DAILY_LOSS_PCT',
        'EMA_FAST_PERIOD', 'EMA_SLOW_PERIOD', 'RSI_PERIOD', 'RSI_OVERBOUGHT', 'RSI_OVERSOLD',
        'MAX_SPREAD_POINTS', 'API_PORT',
        'LONDON_START_HOUR', 'LONDON_END_HOUR', 'NY_START_HOUR', 'NY_END_HOUR'
    ]
    for var in vars_to_clear:
        os.environ.pop(var, None)


# ============== Helper Strategies ==============

@st.composite
def valid_database_url(draw):
    """Generate valid PostgreSQL connection strings."""
    host = draw(st.text(min_size=1, max_size=50))
    port = draw(st.integers(min_value=1, max_value=65535))
    db = draw(st.text(min_size=1, max_size=50))
    user = draw(st.text(min_size=1, max_size=50))
    pwd = draw(st.text(min_size=1, max_size=100))
    return f"postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{db}"


@st.composite
def valid_redis_url(draw):
    """Generate valid Redis connection strings."""
    host = draw(st.text(min_size=1, max_size=50))
    port = draw(st.integers(min_value=1, max_value=65535))
    db = draw(st.integers(min_value=0, max_value=16))
    return f"redis://{host}:{port}/{db}"


@st.composite
def valid_auth_token(draw):
    """Generate valid auth tokens."""
    return draw(st.text(min_size=1, max_size=256))


# ============== Out-of-Bounds Value Strategies ==============

@st.composite
def out_of_bounds_lot_size(draw):
    """Generate lot sizes outside [0.01, 10.0]."""
    return draw(st.one_of(
        st.floats(min_value=0.0001, max_value=0.0099, exclude_min=True),
        st.floats(min_value=10.0001, max_value=100.0),
        st.just(0.0),  # exactly at lower bound (should fail)
    )).filter(lambda x: x < 0.01 or x > 10.0)


@st.composite
def out_of_bounds_sl_tp(draw):
    """Generate SL/TP values outside [10, 1000]."""
    return draw(st.one_of(
        st.integers(min_value=1, max_value=9),  # below minimum
        st.integers(min_value=1001, max_value=5000)  # above maximum
    ))


@st.composite
def out_of_bounds_max_daily_loss(draw):
    """Generate max_daily_loss_pct outside [0.1, 100.0]."""
    return draw(st.one_of(
        st.floats(min_value=0.001, max_value=0.099, exclude_min=True),
        st.floats(min_value=100.001, max_value=500.0),
        st.just(0.0)  # exactly at lower bound (should fail)
    )).filter(lambda x: x < 0.1 or x > 100.0)


@st.composite
def out_of_bounds_indicator_periods(draw):
    """Generate indicator periods outside [2, 200]."""
    return draw(st.one_of(
        st.integers(min_value=0, max_value=1),  # below minimum
        st.integers(min_value=201, max_value=500)  # above maximum
    ))


@st.composite
def out_of_bounds_session_hours(draw):
    """Generate session hours outside [0, 23]."""
    return draw(st.one_of(
        st.integers(min_value=-10, max_value=-1),
        st.integers(min_value=24, max_value=100)
    ))


@st.composite
def out_of_bounds_api_port(draw):
    """Generate API ports outside [1, 65535]."""
    return draw(st.one_of(
        st.integers(min_value=0, max_value=0),  # 0 is invalid
        st.integers(min_value=65536, max_value=100000)
    ))


# ============== Test: Out-of-Bounds Values ==============

def test_out_of_bounds_lot_size():
    """Config with lot_size outside [0.01, 10.0] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['LOT_SIZE'] = '0.005'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'lot_size' in str(exc_info.value)


def test_out_of_bounds_stop_loss():
    """Config with stop_loss_points outside [10, 1000] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['STOP_LOSS_POINTS'] = '5'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'stop_loss_points' in str(exc_info.value)


def test_out_of_bounds_take_profit():
    """Config with take_profit_points outside [10, 1000] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['TAKE_PROFIT_POINTS'] = '5000'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'take_profit_points' in str(exc_info.value)


def test_out_of_bounds_max_daily_loss():
    """Config with max_daily_loss_pct outside [0.1, 100.0] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['MAX_DAILY_LOSS_PCT'] = '0.05'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'max_daily_loss_pct' in str(exc_info.value)


def test_out_of_bounds_ema_fast_period():
    """Config with ema_fast_period outside [2, 200] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['EMA_FAST_PERIOD'] = '1'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'ema_fast_period' in str(exc_info.value)


def test_out_of_bounds_rsi_period():
    """Config with rsi_period outside [2, 200] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['RSI_PERIOD'] = '1'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'rsi_period' in str(exc_info.value)


def test_out_of_bounds_rsi_overbought():
    """Config with rsi_overbought outside [50, 99] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['RSI_OVERBOUGHT'] = '30'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'rsi_overbought' in str(exc_info.value)


def test_out_of_bounds_rsi_oversold():
    """Config with rsi_oversold outside [1, 50] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['RSI_OVERSOLD'] = '60'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'rsi_oversold' in str(exc_info.value)


def test_out_of_bounds_session_start_hour():
    """Config with session start hour outside [0, 23] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['LONDON_START_HOUR'] = '25'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'london_start_hour' in str(exc_info.value)


def test_out_of_bounds_api_port():
    """Config with api_port outside [1, 65535] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['API_PORT'] = '70000'
    
    with pytest.raises(ValidationError) as exc_info:
        from app.config import Settings
        Settings()
    
    assert 'api_port' in str(exc_info.value)


# ============== Property-Based Tests ==============

@given(
    lot_size=st.floats(min_value=0.0001, max_value=100.0).filter(lambda x: x < 0.01 or x > 10.0)
)
@hypothesis_settings(max_examples=10)
def test_property_out_of_bounds_lot_size(lot_size):
    """Property: lot_size outside [0.01, 10.0] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['LOT_SIZE'] = str(lot_size)
    
    with pytest.raises(ValidationError):
        from app.config import Settings
        Settings()


@given(
    sl_tp=st.integers(min_value=1, max_value=5000).filter(lambda x: x < 10 or x > 1000)
)
@hypothesis_settings(max_examples=10)
def test_property_out_of_bounds_sl_tp(sl_tp):
    """Property: SL/TP outside [10, 1000] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['STOP_LOSS_POINTS'] = str(sl_tp)
    os.environ['TAKE_PROFIT_POINTS'] = str(sl_tp)
    
    with pytest.raises(ValidationError):
        from app.config import Settings
        Settings()


@given(
    period=st.integers(min_value=0, max_value=500).filter(lambda x: x < 2 or x > 200)
)
@hypothesis_settings(max_examples=10)
def test_property_out_of_bounds_indicator_period(period):
    """Property: indicator periods outside [2, 200] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['EMA_FAST_PERIOD'] = str(period)
    os.environ['EMA_SLOW_PERIOD'] = str(period)
    os.environ['RSI_PERIOD'] = str(period)
    
    with pytest.raises(ValidationError):
        from app.config import Settings
        Settings()


@given(
    hour=st.integers(min_value=-10, max_value=100).filter(lambda x: x < 0 or x > 23)
)
@hypothesis_settings(max_examples=10)
def test_property_out_of_bounds_session_hour(hour):
    """Property: session hours outside [0, 23] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['LONDON_START_HOUR'] = str(hour)
    os.environ['LONDON_END_HOUR'] = str(hour)
    os.environ['NY_START_HOUR'] = str(hour)
    os.environ['NY_END_HOUR'] = str(hour)
    
    with pytest.raises(ValidationError):
        from app.config import Settings
        Settings()


@given(
    port=st.integers(min_value=0, max_value=100000).filter(lambda x: x < 1 or x > 65535)
)
@hypothesis_settings(max_examples=10)
def test_property_out_of_bounds_api_port(port):
    """Property: api_port outside [1, 65535] should fail validation."""
    clear_env()
    set_valid_env()
    os.environ['API_PORT'] = str(port)
    
    with pytest.raises(ValidationError):
        from app.config import Settings
        Settings()


# ============== Test: Valid Configurations ==============

def test_valid_config_with_all_required_fields():
    """Config with all required fields and valid bounds should succeed."""
    clear_env()
    set_valid_env()
    # Clear any optional env vars
    os.environ.pop('LOT_SIZE', None)
    os.environ.pop('STOP_LOSS_POINTS', None)
    os.environ.pop('TAKE_PROFIT_POINTS', None)
    
    from app.config import Settings
    settings = Settings()
    
    # Verify required fields are set
    assert settings.database_url == VALID_DB_URL
    assert settings.redis_url == VALID_REDIS_URL
    assert settings.auth_token == VALID_AUTH_TOKEN


def test_valid_config_with_custom_values():
    """Config with custom valid values should succeed."""
    clear_env()
    set_valid_env()
    os.environ['LOT_SIZE'] = '0.50'
    os.environ['STOP_LOSS_POINTS'] = '200'
    os.environ['TAKE_PROFIT_POINTS'] = '300'
    os.environ['MAX_DAILY_LOSS_PCT'] = '5.0'
    
    from app.config import Settings
    settings = Settings()
    
    # Verify custom values
    assert settings.lot_size == 0.50
    assert settings.stop_loss_points == 200
    assert settings.take_profit_points == 300
    assert settings.max_daily_loss_pct == 5.0


def test_valid_config_indicator_periods():
    """Config with indicator periods in valid ranges should succeed."""
    clear_env()
    set_valid_env()
    os.environ['EMA_FAST_PERIOD'] = '10'
    os.environ['EMA_SLOW_PERIOD'] = '30'
    os.environ['RSI_PERIOD'] = '20'
    
    from app.config import Settings
    settings = Settings()
    
    # Verify values
    assert settings.ema_fast_period == 10
    assert settings.ema_slow_period == 30
    assert settings.rsi_period == 20


def test_default_values_when_not_specified():
    """Config with only required fields should use defaults for optional fields."""
    clear_env()
    set_valid_env()
    # Clear all optional env vars
    optional_vars = [
        'LOT_SIZE', 'STOP_LOSS_POINTS', 'TAKE_PROFIT_POINTS', 'MAX_DAILY_LOSS_PCT',
        'EMA_FAST_PERIOD', 'EMA_SLOW_PERIOD', 'RSI_PERIOD', 'RSI_OVERBOUGHT', 'RSI_OVERSOLD',
        'MAX_SPREAD_POINTS', 'API_PORT'
    ]
    for var in optional_vars:
        os.environ.pop(var, None)
    
    from app.config import Settings
    settings = Settings()
    
    # Verify defaults are applied
    assert settings.lot_size == 0.10
    assert settings.stop_loss_points == 100
    assert settings.take_profit_points == 150
    assert settings.max_daily_loss_pct == 3.0
    assert settings.ema_fast_period == 9
    assert settings.ema_slow_period == 21
    assert settings.rsi_period == 14
    assert settings.rsi_overbought == 70
    assert settings.rsi_oversold == 30
    assert settings.max_spread_points == 40
    assert settings.api_port == 8000
