"""
chart_export.py
----------------
Writes the latest candle + indicator data to small JSON files inside
docs/, which the GitHub Pages chart (docs/index.html) reads directly.

Called from main.py after each symbol is processed, so the chart data
refreshes on the same 5-minute cadence as the alert checks.
"""

import json
import os

import config

DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")

# Maps a display symbol to the JSON filename the chart page expects
_FILENAME_MAP = {
    "BTC/USDT": "btc_data.json",
    "XAU/USD": "gold_data.json",
}


def export_chart_data(symbol: str, df, max_candles: int = 150):
    """
    Writes the last `max_candles` rows of an indicator-enriched DataFrame
    (must have columns: open_time, open, high, low, close, rsi, ma) to
    docs/<symbol>_data.json in the shape the chart page expects.
    """
    filename = _FILENAME_MAP.get(symbol)
    if not filename:
        return  # unknown symbol, nothing to export

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
        "interval": config.CANDLE_INTERVAL,
        "rsi_length": config.RSI_LENGTH,
        "rsi_oversold": config.RSI_OVERSOLD,
        "rsi_overbought": config.RSI_OVERBOUGHT,
        "ma_length": config.MA_LENGTH,
        "ma_type": config.MA_TYPE,
        "candles": candles,
    }

    path = os.path.join(DOCS_DIR, filename)
    with open(path, "w") as f:
        json.dump(payload, f)
