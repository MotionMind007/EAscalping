"""RSI (Relative Strength Index) calculator — pure function.

Calculates RSI using Wilder's smoothing method. Used by the Signal Engine
for momentum confirmation of EMA crossover signals.

Requirements: 4.1
"""


def calculate_rsi(prices: list[float], period: int) -> list[float]:
    """Calculate Relative Strength Index using Wilder's smoothing.

    Requires at least `period + 1` prices (to compute `period` deltas for
    the initial average). After the initial window, uses Wilder's smoothing:
        avg_gain = (prev_avg_gain * (period - 1) + current_gain) / period
        avg_loss = (prev_avg_loss * (period - 1) + current_loss) / period

    Edge case: if avg_loss == 0, RSI = 100 (no downward movement).

    Args:
        prices: List of closing prices (chronological order).
        period: RSI lookback period (typically 14).

    Returns:
        List of RSI values (0–100). Empty list if len(prices) < period + 1.
        Each RSI value starts after the initial `period` deltas are consumed.
    """
    if len(prices) < period + 1:
        return []

    # Calculate price changes (deltas)
    deltas = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]

    # Separate gains and losses
    gains = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]

    # Initial averages (simple average of first `period` values)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Calculate RSI using Wilder's smoothing
    rsi_values: list[float] = []
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    return rsi_values
