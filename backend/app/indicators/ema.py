"""EMA (Exponential Moving Average) calculator — pure function.

Calculates EMA using SMA seed for the first value, then exponential smoothing
for subsequent values. Used by the Signal Engine for crossover detection.

Requirements: 4.1
"""


def calculate_ema(prices: list[float], period: int) -> list[float]:
    """Calculate Exponential Moving Average for a given price series.

    Uses the first `period` prices as an SMA seed, then applies exponential
    smoothing with multiplier = 2 / (period + 1).

    Args:
        prices: List of closing prices (chronological order).
        period: EMA lookback period (e.g., 9 or 21).

    Returns:
        List of EMA values. Empty list if len(prices) < period.
        The first EMA value corresponds to index `period - 1` in the original prices.
    """
    if len(prices) < period:
        return []

    multiplier = 2.0 / (period + 1)

    # SMA seed: average of first `period` prices
    ema_values = [sum(prices[:period]) / period]

    # Exponential smoothing for remaining prices
    for price in prices[period:]:
        ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])

    return ema_values
