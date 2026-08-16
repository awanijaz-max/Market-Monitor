"""
chart_export.py
----------------
Writes the latest candle + indicator data to small JSON files inside
docs/, which the GitHub Pages chart (docs/index.html) reads directly.

Called from main.py after each (symbol, timeframe) pair is processed,
so the chart data refreshes on the same 5-minute cadence as the alert
checks. One JSON file is written per (symbol, timeframe) combination —
e.g. btc_data_1m.json, btc_data_1h.json, gold_data_4h.json — so the
chart's timeframe selector can load exactly the file it needs.
"""

import json
import os

import config

DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")

# Maps a display symbol to the filename PREFIX used for its exported files
_SYMBOL_PREFIX = {
    "BTC/USDT": "btc",
    "XAU/USD": "gold",
}


def chart_data_filename(symbol: str, interval: str) -> str:
    """The exact filename a given (symbol, interval) pair exports to —
    also used by anything that needs to reference the file by name."""
    prefix = _SYMBOL_PREFIX.get(symbol, symbol.lower().replace("/", "_"))
    return f"{prefix}_data_{interval}.json"


def export_chart_data(symbol: str, interval: str, df, max_candles: int = 150):
    """
    Writes the last `max_candles` rows of an indicator-enriched DataFrame
    (must have columns: open_time, open, high, low, close, rsi, ma) to
    docs/<symbol>_data_<interval>.json in the shape the chart page expects.
    """
    os.makedirs(DOCS_DIR, exist_ok=True)
    tail = df.tail(max_candles)

    candles = []
    for _, row in tail.iterrows():
        candles.append({
            # Lightweight Charts wants unix seconds, not ms
            "time": int(row["open_time"].timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "rsi": None if row.get("rsi") != row.get("rsi") else float(row["rsi"]),  # NaN check
            "ma": None if row.get("ma") != row.get("ma") else float(row["ma"]),
        })

    payload = {
        "symbol": symbol,
        "interval": interval,
        "rsi_length": config.RSI_LENGTH,
        "rsi_oversold": config.RSI_OVERSOLD,
        "rsi_overbought": config.RSI_OVERBOUGHT,
        "ma_length": config.MA_LENGTH,
        "ma_type": config.MA_TYPE,
        "candles": candles,
    }

    path = os.path.join(DOCS_DIR, chart_data_filename(symbol, interval))
    with open(path, "w") as f:
        json.dump(payload, f)
