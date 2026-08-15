"""
indicators.py
-------------
Wraps pandas-ta (pure Python — no C-library compilation needed, so it
installs cleanly on free hosts like GitHub Actions runners) to compute
the technical indicators used by the alert conditions.

Add new indicators here and they become available to alert_engine.py
without touching the rest of the pipeline.
"""

import pandas as pd
import pandas_ta as ta

import config


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes a raw OHLCV DataFrame and appends indicator columns in place.
    Returns the same DataFrame (mutated) for convenient chaining.
    """
    df = df.copy()

    # --- RSI ---
    df["rsi"] = ta.rsi(df["close"], length=config.RSI_LENGTH)

    # --- Moving average (SMA or EMA, per config.MA_TYPE) ---
    if config.MA_TYPE.lower() == "ema":
        df["ma"] = ta.ema(df["close"], length=config.MA_LENGTH)
    else:
        df["ma"] = ta.sma(df["close"], length=config.MA_LENGTH)

    return df


# ---------------------------------------------------------------------------
# Example of how to bolt on more indicators later — just add a function
# here and call it from add_indicators(), e.g.:
#
# def add_macd(df):
#     macd = ta.macd(df["close"])
#     return pd.concat([df, macd], axis=1)
# ---------------------------------------------------------------------------
