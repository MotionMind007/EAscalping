"""Property-based tests for payload validation.

Validates that all endpoints properly reject payloads with missing/invalid fields
by returning HTTP 422 status codes. Uses Hypothesis to generate random invalid payloads.

**Validates: Requirements 1.12**
"""
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models.requests import (
    CandlePayload,
    HeartbeatPayload,
    MT5DisconnectPayload,
    MT5ReconnectPayload,
    OrphanPayload,
    PositionKnownRequest,
    PositionStatusPayload,
    RecoveryPayload,
    TickItem,
    TickPayload,
    TradeResultPayload,
    TransitionRequest,
)


# ─── TickItem Validation ──────────────────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_missing_timestamp_should_fail(timestamp):
    """TickItem with missing timestamp should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp=timestamp, bid=1.0, ask=1.0, spread=0)
    assert "timestamp" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_missing_bid_should_fail(bid):
    """TickItem with missing bid should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp="2024-01-15T10:30:00Z", bid=bid, ask=1.0, spread=0)
    assert "bid" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_missing_ask_should_fail(ask):
    """TickItem with missing ask should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp="2024-01-15T10:30:00Z", bid=1.0, ask=ask, spread=0)
    assert "ask" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_missing_spread_should_fail(spread):
    """TickItem with missing spread should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp="2024-01-15T10:30:00Z", bid=1.0, ask=1.0, spread=spread)
    assert "spread" in str(exc_info.value)


@given(st.floats())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_wrong_timestamp_type_should_fail(timestamp):
    """TickItem with wrong timestamp type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp=timestamp, bid=1.0, ask=1.0, spread=0)
    assert "timestamp" in str(exc_info.value)


@given(st.text())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_wrong_bid_type_should_fail(bid):
    """TickItem with wrong bid type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp="2024-01-15T10:30:00Z", bid=bid, ask=1.0, spread=0)
    assert "bid" in str(exc_info.value)


@given(st.text())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_wrong_spread_type_should_fail(spread):
    """TickItem with wrong spread type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp="2024-01-15T10:30:00Z", bid=1.0, ask=1.0, spread=spread)
    assert "spread" in str(exc_info.value)


@given(st.integers(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_negative_spread_should_fail(spread):
    """TickItem with negative spread should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp="2024-01-15T10:30:00Z", bid=1.0, ask=1.0, spread=spread)
    assert "spread" in str(exc_info.value)


@given(st.floats(max_value=0))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_zero_bid_should_fail(bid):
    """TickItem with bid=0 should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp="2024-01-15T10:30:00Z", bid=bid, ask=1.0, spread=0)
    assert "bid" in str(exc_info.value)


@given(st.floats(max_value=0))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_item_zero_ask_should_fail(ask):
    """TickItem with ask=0 should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickItem(timestamp="2024-01-15T10:30:00Z", bid=1.0, ask=ask, spread=0)
    assert "ask" in str(exc_info.value)
# ─── TickPayload Validation ───────────────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_payload_missing_symbol_should_fail(symbol):
    """TickPayload with missing symbol should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickPayload(symbol=symbol, ticks=[])
    assert "symbol" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_payload_missing_ticks_should_fail(ticks):
    """TickPayload with missing ticks should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickPayload(symbol="XAUUSD", ticks=ticks)
    assert "ticks" in str(exc_info.value)


@given(st.text(min_size=21, max_size=50))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_payload_symbol_too_long_should_fail(symbol):
    """TickPayload with symbol > 20 chars should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickPayload(symbol=symbol, ticks=[])
    assert "symbol" in str(exc_info.value)


@given(st.text(max_size=0))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_payload_symbol_empty_should_fail(symbol):
    """TickPayload with empty symbol should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickPayload(symbol=symbol, ticks=[])
    assert "symbol" in str(exc_info.value)


@given(st.just([]))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_payload_empty_ticks_should_fail(ticks):
    """TickPayload with empty ticks array should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickPayload(symbol="XAUUSD", ticks=ticks)
    assert "ticks" in str(exc_info.value)


@given(st.integers())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_tick_payload_wrong_symbol_type_should_fail(symbol):
    """TickPayload with wrong symbol type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TickPayload(symbol=symbol, ticks=[])
    assert "symbol" in str(exc_info.value)
# ─── CandlePayload Validation ─────────────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_candle_payload_missing_symbol_should_fail(symbol):
    """CandlePayload with missing symbol should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CandlePayload(
            symbol=symbol,
            timeframe="M1",
            timestamp="2024-01-15T10:30:00Z",
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=100,
        )
    assert "symbol" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_candle_payload_missing_timeframe_should_fail(timeframe):
    """CandlePayload with missing timeframe should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CandlePayload(
            symbol="XAUUSD",
            timeframe=timeframe,
            timestamp="2024-01-15T10:30:00Z",
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=100,
        )
    assert "timeframe" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_candle_payload_missing_open_should_fail(open_price):
    """CandlePayload with missing open should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CandlePayload(
            symbol="XAUUSD",
            timeframe="M1",
            timestamp="2024-01-15T10:30:00Z",
            open=open_price,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=100,
        )
    assert "open" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_candle_payload_missing_volume_should_fail(volume):
    """CandlePayload with missing volume should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CandlePayload(
            symbol="XAUUSD",
            timeframe="M1",
            timestamp="2024-01-15T10:30:00Z",
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=volume,
        )
    assert "volume" in str(exc_info.value)


@given(st.integers())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_candle_payload_wrong_open_type_should_fail(open_price):
    """CandlePayload with wrong open type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CandlePayload(
            symbol="XAUUSD",
            timeframe="M1",
            timestamp="2024-01-15T10:30:00Z",
            open=open_price,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=100,
        )
    assert "open" in str(exc_info.value)


@given(st.floats(max_value=0))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_candle_payload_zero_open_should_fail(open_price):
    """CandlePayload with open=0 should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CandlePayload(
            symbol="XAUUSD",
            timeframe="M1",
            timestamp="2024-01-15T10:30:00Z",
            open=open_price,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=100,
        )
    assert "open" in str(exc_info.value)


@given(st.text())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_candle_payload_wrong_volume_type_should_fail(volume):
    """CandlePayload with wrong volume type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CandlePayload(
            symbol="XAUUSD",
            timeframe="M1",
            timestamp="2024-01-15T10:30:00Z",
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=volume,
        )
    assert "volume" in str(exc_info.value)


@given(st.floats(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_candle_payload_negative_volume_should_fail(volume):
    """CandlePayload with negative volume should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CandlePayload(
            symbol="XAUUSD",
            timeframe="M1",
            timestamp="2024-01-15T10:30:00Z",
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=volume,
        )
    assert "volume" in str(exc_info.value)
# ─── HeartbeatPayload Validation ──────────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_heartbeat_payload_missing_state_should_fail(state):
    """HeartbeatPayload with missing state should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        HeartbeatPayload(
            state=state,
            account_balance=10000.0,
            account_equity=10050.0,
            latency_ms=15,
            mt5_connected=True,
            spread=25,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "state" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_heartbeat_payload_missing_account_balance_should_fail(balance):
    """HeartbeatPayload with missing account_balance should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        HeartbeatPayload(
            state="WAIT_SESSION",
            account_balance=balance,
            account_equity=10050.0,
            latency_ms=15,
            mt5_connected=True,
            spread=25,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "account_balance" in str(exc_info.value)


@given(st.integers())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_heartbeat_payload_wrong_state_type_should_fail(state):
    """HeartbeatPayload with wrong state type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        HeartbeatPayload(
            state=state,
            account_balance=10000.0,
            account_equity=10050.0,
            latency_ms=15,
            mt5_connected=True,
            spread=25,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "state" in str(exc_info.value)


@given(st.just("INVALID_STATE"))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_heartbeat_payload_invalid_state_value_should_fail(state):
    """HeartbeatPayload with invalid state value should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        HeartbeatPayload(
            state=state,
            account_balance=10000.0,
            account_equity=10050.0,
            latency_ms=15,
            mt5_connected=True,
            spread=25,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "state" in str(exc_info.value)


@given(st.floats(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_heartbeat_payload_negative_account_balance_should_fail(balance):
    """HeartbeatPayload with negative account_balance should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        HeartbeatPayload(
            state="WAIT_SESSION",
            account_balance=balance,
            account_equity=10050.0,
            latency_ms=15,
            mt5_connected=True,
            spread=25,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "account_balance" in str(exc_info.value)


@given(st.floats(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_heartbeat_payload_negative_account_equity_should_fail(equity):
    """HeartbeatPayload with negative account_equity should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        HeartbeatPayload(
            state="WAIT_SESSION",
            account_balance=10000.0,
            account_equity=equity,
            latency_ms=15,
            mt5_connected=True,
            spread=25,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "account_equity" in str(exc_info.value)


@given(st.floats(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_heartbeat_payload_negative_latency_ms_should_fail(latency):
    """HeartbeatPayload with negative latency_ms should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        HeartbeatPayload(
            state="WAIT_SESSION",
            account_balance=10000.0,
            account_equity=10050.0,
            latency_ms=latency,
            mt5_connected=True,
            spread=25,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "latency_ms" in str(exc_info.value)
# ─── TransitionRequest Validation ─────────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_transition_request_missing_current_state_should_fail(state):
    """TransitionRequest with missing current_state should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TransitionRequest(
            current_state=state,
            requested_state="CHECK_RISK",
            reason="test",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "current_state" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_transition_request_missing_reason_should_fail(reason):
    """TransitionRequest with missing reason should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TransitionRequest(
            current_state="WAIT_SESSION",
            requested_state="CHECK_RISK",
            reason=reason,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "reason" in str(exc_info.value)


@given(st.integers())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_transition_request_wrong_current_state_type_should_fail(state):
    """TransitionRequest with wrong current_state type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TransitionRequest(
            current_state=state,
            requested_state="CHECK_RISK",
            reason="test",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "current_state" in str(exc_info.value)


@given(st.just("INVALID_STATE"))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_transition_request_invalid_current_state_should_fail(state):
    """TransitionRequest with invalid current_state value should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TransitionRequest(
            current_state=state,
            requested_state="CHECK_RISK",
            reason="test",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "current_state" in str(exc_info.value)


@given(st.just(""))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_transition_request_empty_reason_should_fail(reason):
    """TransitionRequest with empty reason should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TransitionRequest(
            current_state="WAIT_SESSION",
            requested_state="CHECK_RISK",
            reason=reason,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "reason" in str(exc_info.value)


@given(st.integers())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_transition_request_wrong_reason_type_should_fail(reason):
    """TransitionRequest with wrong reason type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TransitionRequest(
            current_state="WAIT_SESSION",
            requested_state="CHECK_RISK",
            reason=reason,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "reason" in str(exc_info.value)
# ─── TradeResultPayload Validation ────────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_trade_result_payload_missing_success_should_fail(success):
    """TradeResultPayload with missing success should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TradeResultPayload(
            success=success,
            command_type="BUY",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "success" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_trade_result_payload_missing_command_type_should_fail(command_type):
    """TradeResultPayload with missing command_type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TradeResultPayload(
            success=True,
            command_type=command_type,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "command_type" in str(exc_info.value)


@given(st.text())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_trade_result_payload_wrong_success_type_should_fail(success):
    """TradeResultPayload with wrong success type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TradeResultPayload(
            success=success,
            command_type="BUY",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "success" in str(exc_info.value)


@given(st.just("INVALID_COMMAND"))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_trade_result_payload_invalid_command_type_should_fail(command_type):
    """TradeResultPayload with invalid command_type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TradeResultPayload(
            success=True,
            command_type=command_type,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "command_type" in str(exc_info.value)


@given(st.integers(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_trade_result_payload_negative_ticket_should_fail(ticket):
    """TradeResultPayload with negative ticket should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TradeResultPayload(
            success=True,
            ticket=ticket,
            command_type="BUY",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "ticket" in str(exc_info.value)


@given(st.floats(max_value=0))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_trade_result_payload_zero_fill_price_should_fail(fill_price):
    """TradeResultPayload with fill_price=0 should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TradeResultPayload(
            success=True,
            ticket=12345,
            fill_price=fill_price,
            command_type="BUY",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "fill_price" in str(exc_info.value)


@given(st.text())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_trade_result_payload_wrong_error_code_type_should_fail(error_code):
    """TradeResultPayload with wrong error_code type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TradeResultPayload(
            success=False,
            error_code=error_code,
            command_type="BUY",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "error_code" in str(exc_info.value)


@given(st.floats(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_trade_result_payload_negative_slippage_should_fail(slippage):
    """TradeResultPayload with negative slippage_points should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TradeResultPayload(
            success=False,
            error_code=123,
            slippage_points=slippage,
            command_type="BUY",
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "slippage_points" in str(exc_info.value)
# ─── PositionStatusPayload Validation ─────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_missing_ticket_should_fail(ticket):
    """PositionStatusPayload with missing ticket should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=ticket,
            symbol="XAUUSD",
            direction="BUY",
            lot_size=0.1,
            open_price=2025.0,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "ticket" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_missing_direction_should_fail(direction):
    """PositionStatusPayload with missing direction should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction=direction,
            lot_size=0.1,
            open_price=2025.0,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "direction" in str(exc_info.value)


@given(st.integers(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_negative_ticket_should_fail(ticket):
    """PositionStatusPayload with negative ticket should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=ticket,
            symbol="XAUUSD",
            direction="BUY",
            lot_size=0.1,
            open_price=2025.0,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "ticket" in str(exc_info.value)


@given(st.just(""))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_empty_symbol_should_fail(symbol):
    """PositionStatusPayload with empty symbol should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=12345,
            symbol=symbol,
            direction="BUY",
            lot_size=0.1,
            open_price=2025.0,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "symbol" in str(exc_info.value)


@given(st.text(min_size=21, max_size=50))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_symbol_too_long_should_fail(symbol):
    """PositionStatusPayload with symbol > 20 chars should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=12345,
            symbol=symbol,
            direction="BUY",
            lot_size=0.1,
            open_price=2025.0,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "symbol" in str(exc_info.value)


@given(st.just("INVALID_DIRECTION"))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_invalid_direction_should_fail(direction):
    """PositionStatusPayload with invalid direction should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction=direction,
            lot_size=0.1,
            open_price=2025.0,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "direction" in str(exc_info.value)


@given(st.just(0))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_zero_lot_size_should_fail(lot_size):
    """PositionStatusPayload with lot_size=0 should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction="BUY",
            lot_size=lot_size,
            open_price=2025.0,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "lot_size" in str(exc_info.value)


@given(st.floats(min_value=10.01))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_lot_size_over_limit_should_fail(lot_size):
    """PositionStatusPayload with lot_size > 10.0 should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction="BUY",
            lot_size=lot_size,
            open_price=2025.0,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "lot_size" in str(exc_info.value)


@given(st.floats(max_value=0))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_status_payload_zero_open_price_should_fail(open_price):
    """PositionStatusPayload with open_price=0 should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionStatusPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction="BUY",
            lot_size=0.1,
            open_price=open_price,
            current_price=2026.0,
            unrealized_pnl=100.0,
            timestamp="2024-01-15T10:30:00Z",
        )
    assert "open_price" in str(exc_info.value)
# ─── OrphanPayload Validation ─────────────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_orphan_payload_missing_ticket_should_fail(ticket):
    """OrphanPayload with missing ticket should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        OrphanPayload(
            ticket=ticket,
            symbol="XAUUSD",
            direction="BUY",
            lot_size=0.1,
            open_price=2025.0,
            open_time="2024-01-15T10:30:00Z",
        )
    assert "ticket" in str(exc_info.value)


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_orphan_payload_missing_direction_should_fail(direction):
    """OrphanPayload with missing direction should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        OrphanPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction=direction,
            lot_size=0.1,
            open_price=2025.0,
            open_time="2024-01-15T10:30:00Z",
        )
    assert "direction" in str(exc_info.value)


@given(st.integers(max_value=-1))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_orphan_payload_negative_ticket_should_fail(ticket):
    """OrphanPayload with negative ticket should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        OrphanPayload(
            ticket=ticket,
            symbol="XAUUSD",
            direction="BUY",
            lot_size=0.1,
            open_price=2025.0,
            open_time="2024-01-15T10:30:00Z",
        )
    assert "ticket" in str(exc_info.value)


@given(st.just(""))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_orphan_payload_empty_symbol_should_fail(symbol):
    """OrphanPayload with empty symbol should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        OrphanPayload(
            ticket=12345,
            symbol=symbol,
            direction="BUY",
            lot_size=0.1,
            open_price=2025.0,
            open_time="2024-01-15T10:30:00Z",
        )
    assert "symbol" in str(exc_info.value)


@given(st.just("INVALID_DIRECTION"))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_orphan_payload_invalid_direction_should_fail(direction):
    """OrphanPayload with invalid direction should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        OrphanPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction=direction,
            lot_size=0.1,
            open_price=2025.0,
            open_time="2024-01-15T10:30:00Z",
        )
    assert "direction" in str(exc_info.value)


@given(st.floats(max_value=0))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_orphan_payload_zero_open_price_should_fail(open_price):
    """OrphanPayload with open_price=0 should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        OrphanPayload(
            ticket=12345,
            symbol="XAUUSD",
            direction="BUY",
            lot_size=0.1,
            open_price=open_price,
            open_time="2024-01-15T10:30:00Z",
        )
    assert "open_price" in str(exc_info.value)
# ─── PositionKnownRequest Validation ──────────────────────────────────────────


@given(st.none())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_known_request_missing_symbol_should_fail(symbol):
    """PositionKnownRequest with missing symbol should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionKnownRequest(symbol=symbol)
    assert "symbol" in str(exc_info.value)


@given(st.just(""))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_known_request_empty_symbol_should_fail(symbol):
    """PositionKnownRequest with empty symbol should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionKnownRequest(symbol=symbol)
    assert "symbol" in str(exc_info.value)


@given(st.text(min_size=21, max_size=50))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_known_request_symbol_too_long_should_fail(symbol):
    """PositionKnownRequest with symbol > 20 chars should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionKnownRequest(symbol=symbol)
    assert "symbol" in str(exc_info.value)


@given(st.integers())
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_position_known_request_wrong_symbol_type_should_fail(symbol):
    """PositionKnownRequest with wrong symbol type should fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        PositionKnownRequest(symbol=symbol)
    assert "symbol" in str(exc_info.value)
