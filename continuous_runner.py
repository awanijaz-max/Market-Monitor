#!/usr/bin/env python3
"""
continuous_runner.py
---------------------
OPTIONAL alternative entry point for a long-lived process (e.g. a free
container that stays running, or your own always-on machine).

Streams BTC candles tick-by-tick over Binance's WebSocket and reacts
the instant a candle CLOSES — lower latency than the polling mode in
main.py, at the cost of needing a process that never exits.

Gold still has to be polled periodically inside the loop, since there
is no genuinely free real-time gold WebSocket.

Run:
    python continuous_runner.py
"""

import logging
import threading
import time

import config
import data_feeds
import indicators
import alert_engine
import notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("continuous_runner")

tracker = alert_engine.StateTracker()

# Rolling in-memory buffer of closed BTC candles, seeded from REST so we
# don't have to wait ~200 candles for the WS stream to fill the window.
btc_history = data_feeds.get_btc_klines()


def on_btc_candle_closed(candle: dict):
    global btc_history
    import pandas as pd

    btc_history = pd.concat([btc_history, pd.DataFrame([candle])], ignore_index=True)
    btc_history = btc_history.tail(config.ROLLING_WINDOW_SIZE).reset_index(drop=True)

    df = indicators.add_indicators(btc_history)
    fired = alert_engine.evaluate("BTC/USDT", config.CANDLE_INTERVAL, df, tracker)
    tracker.save()
    for msg in fired:
        notifier.send_alert(msg)


def gold_polling_loop(poll_seconds: int = 60):
    """Gold has no free real-time WS, so poll it on a timer in a side thread."""
    while True:
        try:
            df = data_feeds.get_gold_klines()
            df = indicators.add_indicators(df)
            fired = alert_engine.evaluate("XAU/USD", config.CANDLE_INTERVAL, df, tracker)
            tracker.save()
            for msg in fired:
                notifier.send_alert(msg)
        except Exception as e:
            log.error("Gold polling loop error: %s", e)
        time.sleep(poll_seconds)


def main():
    gold_thread = threading.Thread(target=gold_polling_loop, daemon=True)
    gold_thread.start()

    btc_feed = data_feeds.BinanceKlineWebSocket(on_closed_candle=on_btc_candle_closed)
    log.info("Starting continuous BTC WebSocket stream + gold polling thread...")
    btc_feed.run_forever()  # blocks forever, auto-reconnects on drop


if __name__ == "__main__":
    main()
