"""
data_feeds.py
-------------
All market data connectors live here. Two acquisition modes are provided
for each asset:

  1. POLLING (REST) — stateless, works perfectly inside a cron job / GitHub
     Action that spins up, runs, and exits. This is the recommended mode
     for the free-hosting roadmap in README.md.

  2. STREAMING (WebSocket) — for BTC only, via Binance's public WS. Use
     this only if you have a machine/process that can stay running
     continuously (see README section 5, "Option A").

Every function returns a pandas DataFrame with columns:
    ['open_time', 'open', 'high', 'low', 'close', 'volume']
sorted oldest -> newest, so downstream code never has to care which
source the candles came from.
"""

import json
import time
import logging
from datetime import datetime, timezone

import pandas as pd
import requests

import config

log = logging.getLogger(__name__)

BINANCE_REST_BASE = "https://data-api.binance.vision"
# NOTE: was api.binance.com, but GitHub Actions runners are hosted on
# US-based servers, and api.binance.com blocks US-origin requests for
# regulatory reasons (HTTP 451). data-api.binance.vision is Binance's
# market-data-only mirror — same response shape, no geo-block, no
# authentication needed either way.
BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"


# ---------------------------------------------------------------------------
# BTC — Binance public REST (no API key required for market data endpoints)
# ---------------------------------------------------------------------------
def get_btc_klines(interval: str = None, limit: int = None) -> pd.DataFrame:
    """
    Pulls recent klines (candlesticks) for BTC/USDT from Binance's public
    REST API. This endpoint requires NO API key and NO authentication —
    it's rate-limited by IP, generously enough for this use case.

    Docs: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
    Note: Binance blocks requests from some regions (incl. US IPs) at the
    network level. If you get connection errors from a US-based host,
    switch to `https://api.binance.us` (same shape, US-compliant) or
    `https://data-api.binance.vision` (market-data-only mirror, no geo-block).
    """
    interval = interval or config.CANDLE_INTERVAL
    limit = limit or config.ROLLING_WINDOW_SIZE

    url = f"{BINANCE_REST_BASE}/api/v3/klines"
    params = {
        "symbol": config.BTC_BINANCE_SYMBOL.upper(),
        "interval": interval,
        "limit": limit,
    }

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df.reset_index(drop=True)


class BinanceKlineWebSocket:
    """
    OPTIONAL continuous-mode feed. Only useful if this script is run as a
    long-lived process (not a cron job), since the socket state disappears
    the moment the process exits.

    Usage:
        feed = BinanceKlineWebSocket(on_closed_candle=my_callback)
        feed.run_forever()   # blocking; run in its own thread if needed
    """

    def __init__(self, symbol: str = None, interval: str = None, on_closed_candle=None):
        self.symbol = (symbol or config.BTC_BINANCE_SYMBOL).lower()
        self.interval = interval or config.CANDLE_INTERVAL
        self.on_closed_candle = on_closed_candle  # callback(dict) fired once per CLOSED candle
        self._ws = None

    def _stream_url(self) -> str:
        return f"{BINANCE_WS_BASE}/{self.symbol}@kline_{self.interval}"

    def run_forever(self):
        import websocket  # imported lazily so it's optional for cron users

        def on_message(ws, message):
            payload = json.loads(message)
            k = payload.get("k", {})
            # Binance sends an update on every tick; 'x' is True only
            # when the candle has actually CLOSED. We only act on closes
            # to avoid evaluating indicators on incomplete candles.
            if k.get("x") is True and self.on_closed_candle:
                candle = {
                    "open_time": pd.to_datetime(k["t"], unit="ms", utc=True),
                    "open": float(k["o"]),
                    "high": float(k["h"]),
                    "low": float(k["l"]),
                    "close": float(k["c"]),
                    "volume": float(k["v"]),
                }
                self.on_closed_candle(candle)

        def on_error(ws, error):
            log.error("Binance WS error: %s", error)

        def on_close(ws, close_status_code, close_msg):
            log.warning("Binance WS closed (%s). Reconnecting in 5s...", close_status_code)
            time.sleep(5)
            self.run_forever()

        self._ws = websocket.WebSocketApp(
            self._stream_url(),
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._ws.run_forever(ping_interval=180, ping_timeout=10)


# ---------------------------------------------------------------------------
# GOLD (XAU/USD) — no genuinely free real-time WS exists without a card.
# Primary: yfinance (unofficial Yahoo Finance wrapper, free, no key, no
#          signup — but data can lag ~1 minute and is best-effort).
# Fallback: TwelveData free tier (requires free signup + API key, but
#           explicitly NO credit card — 800 requests/day on the free plan).
# ---------------------------------------------------------------------------
_YF_INTERVAL_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m", "4h": "60m",  # yfinance has no native 4h; resample 60m -> 4h if needed
    "1d": "1d",
}


def get_gold_klines_yfinance(interval: str = None, limit: int = None) -> pd.DataFrame:
    """Free, keyless gold candles via Yahoo Finance (unofficial, best-effort)."""
    import yfinance as yf

    interval = interval or config.CANDLE_INTERVAL
    limit = limit or config.ROLLING_WINDOW_SIZE
    yf_interval = _YF_INTERVAL_MAP.get(interval, "15m")

    # yfinance intraday intervals only allow short lookback windows;
    # "7d" comfortably covers 200 x 15m candles.
    hist = yf.Ticker(config.GOLD_YF_TICKER).history(period="7d", interval=yf_interval)
    if hist.empty:
        raise RuntimeError("yfinance returned no gold data — market may be closed or ticker blocked.")

    hist = hist.reset_index().rename(columns={
        "Datetime": "open_time", "Date": "open_time",
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    df = hist[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    return df.tail(limit).reset_index(drop=True)


def get_gold_klines_twelvedata(interval: str = None, limit: int = None) -> pd.DataFrame:
    """Fallback gold source using TwelveData's free API key tier."""
    if not config.TWELVEDATA_API_KEY:
        raise RuntimeError("TWELVEDATA_API_KEY is not set — see config.py docstring.")

    interval = interval or config.CANDLE_INTERVAL
    limit = limit or config.ROLLING_WINDOW_SIZE

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "XAU/USD",
        "interval": interval,
        "outputsize": limit,
        "apikey": config.TWELVEDATA_API_KEY,
        "format": "JSON",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()

    if "values" not in payload:
        raise RuntimeError(f"TwelveData error: {payload}")

    df = pd.DataFrame(payload["values"])
    df = df.rename(columns={"datetime": "open_time"})
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["volume"] = df.get("volume", 0).astype(float) if "volume" in df else 0.0
    # TwelveData returns newest-first — flip to oldest-first for consistency
    return df.sort_values("open_time").reset_index(drop=True)


def get_gold_klines(interval: str = None, limit: int = None) -> pd.DataFrame:
    """Tries yfinance first, falls back to TwelveData automatically."""
    try:
        return get_gold_klines_yfinance(interval, limit)
    except Exception as e:
        log.warning("yfinance gold fetch failed (%s) — falling back to TwelveData.", e)
        return get_gold_klines_twelvedata(interval, limit)
