"""Unit tests for EMA and RSI indicator calculations.

Validates against known values and edge cases.
"""
import pytest

from app.indicators.ema import calculate_ema
from app.indicators.rsi import calculate_rsi


class TestCalculateEMA:
    """Tests for the EMA calculator pure function."""

    def test_empty_list_returns_empty(self):
        """No prices → no EMA values."""
        assert calculate_ema([], 9) == []

    def test_fewer_prices_than_period_returns_empty(self):
        """If len(prices) < period, cannot compute EMA."""
        assert calculate_ema([1.0, 2.0, 3.0], 5) == []

    def test_exactly_period_prices_returns_sma(self):
        """With exactly `period` prices, result is just the SMA (single value)."""
        prices = [10.0, 20.0, 30.0]
        result = calculate_ema(prices, 3)
        assert len(result) == 1
        assert result[0] == pytest.approx(20.0)  # (10+20+30)/3

    def test_known_ema_values_period_3(self):
        """Verify EMA calculation against hand-computed values, period=3."""
        prices = [10.0, 11.0, 12.0, 13.0, 14.0]
        # SMA seed: (10+11+12)/3 = 11.0
        # multiplier = 2/(3+1) = 0.5
        # EMA[1] = (13 - 11) * 0.5 + 11 = 12.0
        # EMA[2] = (14 - 12) * 0.5 + 12 = 13.0
        result = calculate_ema(prices, 3)
        assert len(result) == 3
        assert result[0] == pytest.approx(11.0)
        assert result[1] == pytest.approx(12.0)
        assert result[2] == pytest.approx(13.0)

    def test_known_ema_values_period_5(self):
        """Verify EMA with period=5 against known values."""
        prices = [22.0, 22.5, 22.2, 21.8, 22.1, 22.4, 22.7]
        # SMA seed: (22 + 22.5 + 22.2 + 21.8 + 22.1) / 5 = 22.12
        # multiplier = 2 / (5 + 1) = 1/3
        # EMA[1] = (22.4 - 22.12) * (1/3) + 22.12 = 22.21333...
        # EMA[2] = (22.7 - 22.21333) * (1/3) + 22.21333 = 22.37555...
        result = calculate_ema(prices, 5)
        assert len(result) == 3
        assert result[0] == pytest.approx(22.12, abs=0.001)
        assert result[1] == pytest.approx(22.2133, abs=0.001)
        assert result[2] == pytest.approx(22.3756, abs=0.001)

    def test_constant_prices_ema_equals_price(self):
        """If all prices are the same, EMA should equal that price."""
        prices = [50.0] * 20
        result = calculate_ema(prices, 9)
        for val in result:
            assert val == pytest.approx(50.0)

    def test_output_length(self):
        """Output length should be len(prices) - period + 1."""
        prices = [float(i) for i in range(30)]
        period = 9
        result = calculate_ema(prices, period)
        assert len(result) == len(prices) - period + 1


class TestCalculateRSI:
    """Tests for the RSI calculator pure function."""

    def test_empty_list_returns_empty(self):
        """No prices → no RSI values."""
        assert calculate_rsi([], 14) == []

    def test_fewer_prices_than_period_plus_one_returns_empty(self):
        """Need at least period + 1 prices to compute first delta window."""
        assert calculate_rsi([1.0] * 14, 14) == []

    def test_exactly_period_plus_one_returns_empty(self):
        """period + 1 prices gives period deltas but RSI starts after the initial window."""
        # With period=14, need 15 prices for 14 deltas, but RSI starts at index 14 in deltas
        # so we need at least 16 prices (15 deltas, RSI starts at delta[14])
        prices = [float(i) for i in range(15)]
        result = calculate_rsi(prices, 14)
        # 15 prices = 14 deltas, RSI loop: range(14, 14) = empty
        assert result == []

    def test_all_gains_rsi_100(self):
        """If prices only go up, eventually RSI approaches 100."""
        # Create a series where all changes are positive
        prices = [float(i) for i in range(30)]  # 0, 1, 2, ..., 29
        result = calculate_rsi(prices, 14)
        # All deltas are +1, so avg_loss starts at 0 and stays 0 → RSI = 100
        for val in result:
            assert val == pytest.approx(100.0)

    def test_all_losses_rsi_0(self):
        """If prices only go down, RSI should be 0."""
        prices = [float(30 - i) for i in range(30)]  # 30, 29, 28, ..., 1
        result = calculate_rsi(prices, 14)
        # All deltas are -1, so avg_gain starts at 0 and stays 0
        # RS = 0/avg_loss = 0, RSI = 100 - 100/(1+0) = 0
        for val in result:
            assert val == pytest.approx(0.0)

    def test_rsi_range_0_to_100(self):
        """RSI must always be in [0, 100] range."""
        prices = [100.0 + (i % 5) * 0.5 - 1.0 for i in range(50)]
        result = calculate_rsi(prices, 14)
        for val in result:
            assert 0.0 <= val <= 100.0

    def test_known_rsi_value(self):
        """Test RSI against a manually verifiable scenario."""
        # 15 prices where first 14 deltas alternate +1, -1
        # gains: [1,0,1,0,1,0,1,0,1,0,1,0,1,0] → avg = 7/14 = 0.5
        # losses: [0,1,0,1,0,1,0,1,0,1,0,1,0,1] → avg = 7/14 = 0.5
        # Next delta (index 14): need 16 prices
        prices = []
        val = 50.0
        for i in range(16):
            prices.append(val)
            if i % 2 == 0:
                val += 1.0
            else:
                val -= 1.0
        # 16 prices → 15 deltas → RSI loop runs for range(14, 15) = 1 value
        result = calculate_rsi(prices, 14)
        assert len(result) == 1
        # The avg_gain/avg_loss after Wilder's smoothing on the 15th delta
        # RSI should be close to 50 for alternating series
        assert 30.0 <= result[0] <= 70.0  # roughly balanced

    def test_output_length(self):
        """Output length should be len(prices) - period - 1 (deltas - period)."""
        prices = [float(i) for i in range(50)]
        period = 14
        result = calculate_rsi(prices, period)
        # 50 prices → 49 deltas → RSI loop: range(14, 49) = 35 values
        expected_len = len(prices) - 1 - period
        assert len(result) == expected_len
