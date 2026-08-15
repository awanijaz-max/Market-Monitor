"""
config.py
---------
Single source of truth for symbols, timeframes, condition thresholds,
and secrets. Secrets are pulled from environment variables so nothing
sensitive is hard-coded or committed to git.

For local development, create a `.env` file (never commit it) with:
    TELEGRAM_BOT_TOKEN=xxxxx
    TELEGRAM_CHAT_ID=xxxxx
    DISCORD_WEBHOOK_URL=xxxxx
    TWELVEDATA_API_KEY=xxxxx   # optional fallback for gold data

For GitHub Actions hosting, set these same names as encrypted
Repository Secrets instead (Settings -> Secrets and variables -> Actions).
"""

import os
from dotenv import load_dotenv

load_dotenv()  # no-op in production/CI if no .env file exists

# ---------------------------------------------------------------------------
# SYMBOLS & TIMEFRAME
# ---------------------------------------------------------------------------
# Binance uses lowercase pair symbols with no separator, e.g. "btcusdt"
BTC_BINANCE_SYMBOL = "btcusdt"

# yfinance ticker for gold. "XAUUSD=X" was delisted/renamed on Yahoo's end,
# so we use COMEX Gold Futures instead — tracks spot XAU/USD closely (small
# differences from futures roll/contango, usually a few dollars).
GOLD_YF_TICKER = "GC=F"

# Candle interval used for all indicator calculations.
# Binance-native values: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d ...
CANDLE_INTERVAL = "15m"

# How many historical candles to keep in the rolling window.
# Needs to be comfortably larger than the longest indicator lookback.
ROLLING_WINDOW_SIZE = 200

# ---------------------------------------------------------------------------
# INDICATOR / CONDITION THRESHOLDS  (tune freely — this is the "strategy")
# ---------------------------------------------------------------------------
RSI_LENGTH = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MA_LENGTH = 50
MA_TYPE = "ema"  # "sma" or "ema"

# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ntfy.sh — no account needed. The topic name IS the secret, so use a
# long, random string (e.g. generated below), not a guessable word.
NTFY_SERVER = "https://ntfy.sh"
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")

# ---------------------------------------------------------------------------
# OPTIONAL FALLBACK DATA SOURCE FOR GOLD (free tier, no credit card)
# Sign up at https://twelvedata.com/pricing -> "Basic" (free) plan.
# ---------------------------------------------------------------------------
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")

# ---------------------------------------------------------------------------
# STATE PERSISTENCE
# ---------------------------------------------------------------------------
STATE_FILE_PATH = os.path.join(os.path.dirname(__file__), "state.json")
