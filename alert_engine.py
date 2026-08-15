"""
alert_engine.py
----------------
Two responsibilities:

  1. Evaluate multi-condition setups against the latest indicator values
     (a.k.a. "the strategy"). This is deliberately kept as small, pure
     functions so you can add new conditions without touching the
     state-tracking logic.

  2. StateTracker — guarantees each alert fires exactly ONCE per trigger
     event, not on every tick/poll while the condition remains true.
     It does this with EDGE DETECTION: an alert fires only on the
     False -> True transition of a condition, and resets once the
     condition goes back to False. State is persisted to a small JSON
     file so it survives between runs (important for the GitHub Actions
     / cron hosting mode, where the process exits after every run).
"""

import json
import os
import logging
from dataclasses import dataclass
from typing import Callable, Dict

import pandas as pd

import config
import levels_feed

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CONDITION DEFINITIONS
# ---------------------------------------------------------------------------
@dataclass
class Condition:
    name: str                          # unique key, used in state.json and alert text
    check: Callable[[pd.DataFrame], bool]   # receives the full indicator DataFrame
    message: str                       # human-readable alert text


def _rsi_oversold_and_crossing_above_ma(df: pd.DataFrame) -> bool:
    """
    Example multi-condition setup:
      - RSI on the just-closed candle is below the oversold threshold
      - AND price has just crossed above the moving average
        (previous close was <= MA, current close is > MA)

    Both legs must be true on the SAME closed candle.
    """
    if len(df) < 2:
        return False

    prev, curr = df.iloc[-2], df.iloc[-1]

    if pd.isna(curr["rsi"]) or pd.isna(curr["ma"]) or pd.isna(prev["ma"]):
        return False  # not enough warm-up data yet

    rsi_condition = curr["rsi"] < config.RSI_OVERSOLD
    cross_condition = (prev["close"] <= prev["ma"]) and (curr["close"] > curr["ma"])

    return bool(rsi_condition and cross_condition)


def _rsi_overbought_and_crossing_below_ma(df: pd.DataFrame) -> bool:
    """Mirror-image bearish setup — kept as a second worked example."""
    if len(df) < 2:
        return False

    prev, curr = df.iloc[-2], df.iloc[-1]

    if pd.isna(curr["rsi"]) or pd.isna(curr["ma"]) or pd.isna(prev["ma"]):
        return False

    rsi_condition = curr["rsi"] > config.RSI_OVERBOUGHT
    cross_condition = (prev["close"] >= prev["ma"]) and (curr["close"] < curr["ma"])

    return bool(rsi_condition and cross_condition)


def build_conditions() -> list:
    """
    The registry of STATIC (always-present) conditions. TO ADD A NEW
    SETUP: 1) write a `_your_condition(df) -> bool` function above,
    2) append a Condition(...) entry below. Nothing else needs to change.

    Dynamic conditions (drawn MT5 levels) are built separately by
    build_level_cross_conditions(), since they come and go as you draw/
    delete lines rather than being fixed at code-writing time.
    """
    return [
        Condition(
            name="rsi_oversold_bullish_ma_cross",
            check=_rsi_oversold_and_crossing_above_ma,
            message="RSI oversold + bullish MA cross on {symbol} ({interval}). "
                    "RSI={rsi:.1f}, Close={close:.2f}, MA={ma:.2f}",
        ),
        Condition(
            name="rsi_overbought_bearish_ma_cross",
            check=_rsi_overbought_and_crossing_below_ma,
            message="RSI overbought + bearish MA cross on {symbol} ({interval}). "
                    "RSI={rsi:.1f}, Close={close:.2f}, MA={ma:.2f}",
        ),
    ]


def _make_level_cross_check(level_price: float):
    """
    Returns a check() function (closes over level_price) that fires when
    the previous close and current close sit on OPPOSITE sides of the
    level — i.e. price just crossed it, in either direction.
    """
    def check(df: pd.DataFrame) -> bool:
        if len(df) < 2:
            return False
        prev_close = df.iloc[-2]["close"]
        curr_close = df.iloc[-1]["close"]
        # Sign change between (prev - level) and (curr - level) means a
        # crossing happened this candle. Exactly touching the level
        # (product == 0) is deliberately not treated as a cross.
        return bool((prev_close - level_price) * (curr_close - level_price) < 0)
    return check


def build_level_cross_conditions(levels: list) -> list:
    """
    Turns MT5-drawn levels (from levels_feed.read_levels()) into
    Condition objects, one per level, each firing once when price
    crosses it in either direction. Safe to call with an empty list
    (e.g. MT5 not running) — just returns no extra conditions that run.
    """
    conditions = []
    for lvl in levels:
        name = lvl.get("name", "unnamed")
        price = lvl.get("price")
        level_type = lvl.get("type", "level")
        if price is None:
            continue

        level_price = float(price)
        conditions.append(Condition(
            name=f"mt5_level_cross::{name}",
            check=_make_level_cross_check(level_price),
            message=(
                f"Price crossed your drawn {level_type} \"{name}\" "
                f"(level={level_price:.2f}) on "
                "{symbol} ({interval}). Close={close:.2f}"
            ),
        ))
    return conditions


# ---------------------------------------------------------------------------
# STATE TRACKER — fire-once-per-event guarantee
# ---------------------------------------------------------------------------
class StateTracker:
    """
    Persists a {symbol: {condition_name: bool}} map to disk. An alert is
    only dispatched on the False -> True edge, so re-running the checker
    every 5 minutes while a condition stays true won't spam you.
    """

    def __init__(self, path: str = None):
        self.path = path or config.STATE_FILE_PATH
        self._state: Dict[str, Dict[str, bool]] = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Could not read state file (%s) — starting fresh.", e)
        return {}

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self._state, f, indent=2)

    def should_fire(self, symbol: str, condition_name: str, is_active: bool) -> bool:
        """
        Returns True exactly once per False->True transition.
        Call this once per (symbol, condition) per run, and always call
        `save()` after processing all symbols/conditions for the run.
        """
        symbol_state = self._state.setdefault(symbol, {})
        was_active = symbol_state.get(condition_name, False)

        symbol_state[condition_name] = is_active  # record current state regardless

        return is_active and not was_active


# ---------------------------------------------------------------------------
# HIGH-LEVEL ENTRY POINT used by main.py
# ---------------------------------------------------------------------------
def evaluate(symbol: str, interval: str, df: pd.DataFrame, tracker: StateTracker) -> list:
    """
    Runs every registered condition against `df` — both the static
    RSI/MA conditions and, if this is the gold symbol, any live-drawn
    MT5 levels — updates the tracker, and returns formatted alert
    strings for conditions that JUST transitioned to active. Does NOT
    call tracker.save() — the caller controls when to persist (usually
    once, after all symbols).
    """
    fired_messages = []
    latest = df.iloc[-1]

    all_conditions = list(build_conditions())

    # MT5 level-cross conditions only make sense for the symbol MT5 is
    # actually showing you (gold, in the current setup) — reading them
    # is a no-op (empty list) if MT5/the EA isn't running, so this is
    # always safe to call regardless of hosting environment.
    if symbol == "XAU/USD":
        levels = levels_feed.read_levels()
        all_conditions.extend(build_level_cross_conditions(levels))

    for cond in all_conditions:
        is_active = cond.check(df)
        if tracker.should_fire(symbol, cond.name, is_active):
            fired_messages.append(cond.message.format(
                symbol=symbol,
                interval=interval,
                rsi=latest.get("rsi", float("nan")),
                close=latest["close"],
                ma=latest.get("ma", float("nan")),
            ))

    return fired_messages
