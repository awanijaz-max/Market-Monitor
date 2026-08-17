"""
levels_feed.py
---------------
Reads levels_export.json, written by the MQL5 LevelExporter Expert
Advisor (see mt5_bridge/LevelExporter.mq5), and hands them to
alert_engine.py as crossable price levels.

This only works while MT5 desktop is running, logged in, and has the
LevelExporter EA attached to a chart — see mt5_bridge/README.md for
the full setup walkthrough.
"""

import json
import logging
import os

log = logging.getLogger(__name__)

# Fixed path MQL5's FILE_COMMON flag always writes to on Windows,
# regardless of which broker/terminal instance is running.
DEFAULT_LEVELS_PATH = os.path.expandvars(
    r"%APPDATA%\MetaQuotes\Terminal\Common\Files\levels_export.json"
)


def read_levels(path: str = None) -> list:
    """
    Returns a list of dicts like:
        {"name": "...", "type": "hline"/"trendline"/"fibo", "price": float}
    Returns an empty list (never raises) if MT5 isn't running, the EA
    isn't attached, or the file is momentarily mid-write — callers
    should treat "no levels" as a normal, expected state, not an error.
    """
    path = path or DEFAULT_LEVELS_PATH

    if not os.path.exists(path):
        return []

    try:
        with open(path, "r") as f:
            payload = json.load(f)
        levels = payload.get("levels", [])
    except (json.JSONDecodeError, OSError) as e:
        # Most likely caught the file mid-write by the EA (it re-writes
        # every RefreshSeconds) — just skip this run, next poll will work.
        log.debug("Could not read levels file this run (probably mid-write): %s", e)
        return []

    # Defensive filter (belt-and-suspenders alongside the same filter in
    # LevelExporter.mq5): MT5 auto-generates trade-history marker objects
    # that look like trendlines but aren't real drawn levels — their name
    # contains "->" and/or "#", and their price is always 0. Skip those
    # here too, in case an older/un-updated EA build is still exporting
    # them, so this fixes itself without requiring a recompile.
    filtered = [
        lvl for lvl in levels
        if "->" not in lvl.get("name", "")
        and abs(lvl.get("price", 0)) > 0.00001
    ]
    return filtered
