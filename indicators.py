"""
indicators.py
-------------
Computes RSI and a moving average (SMA/EMA) directly with plain
pandas/numpy — no third-party technical-analysis library.

NOTE: this used to depend on `pandas-ta`, but that package was removed
from PyPI (around Sept 2025) after an ownership transfer to an
unfamiliar maintainer and reports questioning the change as a possible
supply-chain issue (see github.com/xgboosted/pandas-ta-classic/issues/30
for the community discussion). Rather than depend on it — or any
similar drop-in "successor" package with the same trust problem — the
two indicators this project actually needs are implemented directly
below. They're short, auditable, and have zero extra dependencies.

Add new indicators here and they become available to alert_engine.py
without touching the rest of the pipeline.
"""

import pandas as pd

import config


def compute_rsi(close: pd.Series, length: int) -> pd.Series:
    """
    Wilder's RSI — the standard formula (same one used by
    TradingView, MT4/5, and most charting platforms).
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's smoothing is an EWM with alpha = 1/length
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Two edge cases the raw division doesn't handle cleanly:
    #   avg_loss == 0 and avg_gain > 0  -> pure uptrend, RSI must be 100
    #   avg_loss == 0 and avg_gain == 0 -> no movement at all, RSI = 50 (neutral)
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return rsi


def compute_ema(close: pd.Series, length: int) -> pd.Series:
    return close.ewm(span=length, adjust=False).mean()


def compute_sma(close: pd.Series, length: int) -> pd.Series:
    return close.rolling(window=length).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes a raw OHLCV DataFrame and appends indicator columns in place.
    Returns the same DataFrame (mutated) for convenient chaining.
    """
    df = df.copy()

    df["rsi"] = compute_rsi(df["close"], config.RSI_LENGTH)

    if config.MA_TYPE.lower() == "ema":
        df["ma"] = compute_ema(df["close"], config.MA_LENGTH)
    else:
        df["ma"] = compute_sma(df["close"], config.MA_LENGTH)

    return df


# ---------------------------------------------------------------------------
# Example of how to bolt on more indicators later — just add a function
# here and call it from add_indicators(), e.g.:
#
# def compute_macd(close, fast=12, slow=26, signal=9):
#     ema_fast = compute_ema(close, fast)
#     ema_slow = compute_ema(close, slow)
#     macd_line = ema_fast - ema_slow
#     signal_line = macd_line.ewm(span=signal, adjust=False).mean()
#     return macd_line, signal_line
# ---------------------------------------------------------------------------
