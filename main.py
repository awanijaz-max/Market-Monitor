#!/usr/bin/env python3
"""
main.py
-------
Entry point for POLLING mode: fetch latest candles for BTC and Gold,
compute indicators, evaluate conditions, fire alerts on new triggers,
and persist state. Designed to run to completion and exit — perfect
for a cron job / GitHub Actions schedule (see README.md section 5).

Run manually:
    python main.py

Run continuously instead (WebSocket mode) is shown in continuous_runner.py.
"""

import logging
import sys

import config
import data_feeds
import indicators
import alert_engine
import notifier
import chart_export

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


# Each entry: (display_symbol, fetch_function)
SYMBOLS = [
    ("BTC/USDT", data_feeds.get_btc_klines),
    ("XAU/USD", data_feeds.get_gold_klines),
]


def process_symbol(symbol: str, fetch_fn, tracker: alert_engine.StateTracker) -> list:
    """Fetch -> compute indicators -> evaluate conditions for one symbol."""
    try:
        df = fetch_fn(config.CANDLE_INTERVAL, config.ROLLING_WINDOW_SIZE)
    except Exception as e:
        log.error("Failed to fetch data for %s: %s", symbol, e)
        return []

    if df.empty or len(df) < max(config.RSI_LENGTH, config.MA_LENGTH) + 2:
        log.warning("Not enough candles for %s yet (%d rows) — skipping this run.", symbol, len(df))
        return []

    df = indicators.add_indicators(df)

    # Export for the GitHub Pages chart (docs/index.html). Failure here
    # should never take down the actual alert pipeline, so it's isolated.
    try:
        chart_export.export_chart_data(symbol, df)
    except Exception as e:
        log.warning("Chart export failed for %s (alerts unaffected): %s", symbol, e)

    return alert_engine.evaluate(symbol, config.CANDLE_INTERVAL, df, tracker)


def main():
    tracker = alert_engine.StateTracker()
    all_fired = []

    for symbol, fetch_fn in SYMBOLS:
        log.info("Checking %s...", symbol)
        fired = process_symbol(symbol, fetch_fn, tracker)
        all_fired.extend(fired)

    # Persist state ONCE, after processing every symbol, so a crash on
    # symbol #2 doesn't leave symbol #1's state half-written.
    tracker.save()

    if not all_fired:
        log.info("No new triggers this run.")
        return

    for message in all_fired:
        notifier.send_alert(message)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Unhandled error in main() — exiting non-zero so CI marks the run failed.")
        sys.exit(1)
