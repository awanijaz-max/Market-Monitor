# Free Market Monitor — XAU/USD & BTC/USDT

A self-hosted, zero-cost alternative to paid TradingView alert tiers. Polls
free data sources, evaluates multi-condition technical setups server-side,
and pushes Telegram/Discord alerts — with a fire-once-per-event guarantee
so you don't get spammed on every tick.

---

## 1. The Free Tech Stack

| Purpose | Library | Why this one |
|---|---|---|
| Data wrangling | `pandas`, `numpy` | Industry standard, free, MIT/BSD licensed |
| Technical indicators | `pandas-ta` | Pure Python — unlike `TA-Lib`, it needs **no C-library compilation**, so it installs cleanly on free CI runners and free hosts where you can't `apt-get install` system packages |
| HTTP | `requests` | Talks to Binance REST, Telegram, Discord |
| Gold data | `yfinance` | Free, keyless wrapper around Yahoo Finance |
| Env vars | `python-dotenv` | Loads a local `.env` for development only |
| Optional streaming | `websocket-client` | Only needed for the continuous/WebSocket mode |

Install everything:
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Why not TA-Lib?** TA-Lib's Python wrapper depends on a compiled C
library that isn't preinstalled on most free hosts (including GitHub
Actions' default images and PythonAnywhere's free tier), so first-time
setup often fails or needs extra apt packages you may not have permission
to install. `pandas-ta` computes the same indicators (RSI, MA/EMA, MACD,
Bollinger Bands, etc.) in pure Python with zero compiled dependencies —
better fit for a "100% free hosting" constraint. If you later host on a
VM where you control the OS, you can swap it in; `indicators.py` is the
only file that would need to change.

---

## 2. 100% Free Live Data Inputs

### BTC — Binance public REST (no API key)
```
GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=200
```
No signup, no key, no card. Rate-limited by IP but generously enough for
polling every few minutes. If your host's IP is geo-blocked by Binance
(this affects some US datacenter IPs), swap the base URL to either:
- `https://api.binance.us` (US-compliant mirror, same response shape)
- `https://data-api.binance.vision` (market-data-only, no geo-block)

For true real-time (sub-second) BTC data, Binance also offers a free
public WebSocket, no key required:
```
wss://stream.binance.com:9443/ws/btcusdt@kline_15m
```
This is what `data_feeds.BinanceKlineWebSocket` uses in continuous mode.

### Gold (XAU/USD) — no free real-time WS exists without a card
This is the one asset where "100% free" requires a compromise:
- **Primary: `yfinance`**, ticker `XAUUSD=X`. Free, no signup, no key —
  but it's an unofficial Yahoo Finance scraper, so treat it as
  best-effort (occasional gaps, ~1 minute lag). Fine for 15m+ candle
  strategies; not suitable for sub-minute scalping.
- **Fallback: TwelveData free tier.** Sign up at twelvedata.com (free
  account, **no credit card requested**), grab an API key, set it as
  `TWELVEDATA_API_KEY`. Free plan gives 800 requests/day — plenty for
  polling every 5 minutes (288 requests/day). `data_feeds.get_gold_klines()`
  tries yfinance first and falls back to TwelveData automatically if
  yfinance fails.

---

## 3. The Code

Files in this project:

| File | Responsibility |
|---|---|
| `config.py` | Symbols, thresholds, secrets (from env vars) |
| `data_feeds.py` | Binance REST/WS + yfinance/TwelveData connectors |
| `indicators.py` | RSI, MA calculations via `pandas-ta` |
| `alert_engine.py` | Condition definitions + fire-once `StateTracker` |
| `notifier.py` | Telegram + Discord senders |
| `main.py` | **Polling entry point** — use this for cron/GitHub Actions hosting |
| `continuous_runner.py` | **Streaming entry point** — use this only if you have an always-on process/machine |
| `state.json` | Auto-created; tracks which conditions are currently "active" per symbol so alerts fire once per event |

**To add a new condition:** write a `def _my_condition(df) -> bool` function
in `alert_engine.py` and add one `Condition(...)` entry to `build_conditions()`.
Nothing else needs to change — the state tracker and notifier pick it up
automatically.

Run it once locally to test:
```bash
python main.py
```

---

## 4. Free Notification Channels

### Telegram (recommended — simplest setup)
1. Message **@BotFather** on Telegram, send `/newbot`, follow the prompts.
   You'll get a **bot token** like `123456789:ABC-def...`.
2. Message your new bot once (anything), then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   and read your **chat_id** out of the JSON response.
3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (env vars or GitHub Secrets).

Send snippet (already implemented in `notifier.py`):
```python
import requests

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
```

### Discord
1. In your server: **Server Settings -> Integrations -> Webhooks -> New Webhook**.
2. Copy the webhook URL, set it as `DISCORD_WEBHOOK_URL`.

Send snippet:
```python
import requests

def send_discord(message: str):
    requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
```

Both are wired up already — set either (or both) and `notifier.send_alert()`
fans out to whichever is configured.

---

## 5. Free Hosting Roadmap

Honest framing: genuinely free, **card-free**, truly-24/7 *persistent*
process hosting is the hardest part of this constraint — most providers
that keep a process alive continuously (Oracle Cloud, Fly.io, Railway,
Render background workers) now ask for card verification even on their
free tier, and PythonAnywhere's free plan only allows **one scheduled
task per day**, not continuous execution or frequent cron.

The one option that's genuinely free, requires no card, and runs on a
real schedule is **GitHub Actions cron**, so that's what `main.py` and
`.github/workflows/monitor.yml` are built around.

### Recommended: GitHub Actions (polling mode, every 5 minutes)
1. Push this project to a new **public** GitHub repo (public repos get
   2,000+ free Action minutes/month; private repos get a smaller free
   quota that a 5-minute cron will burn through faster).
2. Repo -> **Settings -> Secrets and variables -> Actions** -> add:
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DISCORD_WEBHOOK_URL`
   (and `TWELVEDATA_API_KEY` if you're using the gold fallback).
3. The included workflow (`.github/workflows/monitor.yml`) runs `main.py`
   every 5 minutes, then commits the updated `state.json` back to the
   repo so the fire-once tracker persists between runs.
4. Done — check the **Actions** tab to confirm green runs, and test by
   temporarily loosening a threshold in `config.py` to force a trigger.

Trade-off: this is polling, not tick-by-tick streaming, and GitHub's
cron scheduler is best-effort (can slip a few minutes under load) — fine
for 15m/1h candle strategies, not for sub-minute scalping alerts.

### Alternative: your own always-on machine (streaming mode)
If you have any machine that can stay on (a home PC, a spare Raspberry
Pi, a free-tier VM you already have from elsewhere), run
`continuous_runner.py` instead — it streams BTC in real time over
WebSocket and polls gold every 60 seconds in a background thread. Use
a process supervisor (`tmux`, `screen`, or `systemd`/`pm2`) so it
restarts if it crashes.

### Not recommended, but exists
- **Replit free tier + UptimeRobot ping trick**: keeps a web-facing repl
  "awake" via external pings. No card required, but Replit's free-tier
  policies around this change often and reliability is inconsistent —
  treat as a fallback, not a foundation.
- **PythonAnywhere free tier**: fine for the *one-daily-task* schedule
  or for testing in a console, but not for sub-daily cron without
  upgrading.

---

## Customizing thresholds
Everything strategy-related lives in `config.py` (`RSI_LENGTH`,
`RSI_OVERSOLD`, `MA_LENGTH`, `MA_TYPE`, `CANDLE_INTERVAL`) and
`alert_engine.py` (the actual condition logic). No other file needs to
change to tune or extend the strategy.
