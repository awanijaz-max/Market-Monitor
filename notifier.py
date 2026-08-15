"""
notifier.py
-----------
Free outbound notification channels. All genuinely free forever,
no credit card, no paid tier:

  - Telegram Bot API  (create a bot via @BotFather, get a token — free)
  - Discord Webhook    (Server Settings -> Integrations -> Webhooks — free)
  - ntfy.sh            (no account, no signup, no password at all —
                         just a topic name. https://ntfy.sh)

Set the relevant secrets (see config.py) and just call send_alert().
Every channel is optional — if its config value is blank, it's skipped.
"""

import logging
import requests

import config

log = logging.getLogger(__name__)


def send_telegram(message: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Telegram send failed: %s", e)
        return False


def send_discord(message: str) -> bool:
    if not config.DISCORD_WEBHOOK_URL:
        return False

    payload = {"content": message}
    try:
        resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Discord send failed: %s", e)
        return False


def send_ntfy(message: str) -> bool:
    """
    ntfy.sh needs no account, no key, no password — just a topic name that
    acts as a de facto shared secret. Anyone who knows/guesses the topic
    name can read or publish to it, so config.NTFY_TOPIC should be long
    and random (not something guessable like "gold-alerts").
    """
    if not config.NTFY_TOPIC:
        return False

    url = f"{config.NTFY_SERVER}/{config.NTFY_TOPIC}"
    try:
        resp = requests.post(
            url,
            data=message.encode("utf-8"),
            headers={"Title": "Market Monitor Alert", "Priority": "high"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("ntfy send failed: %s", e)
        return False


def send_alert(message: str):
    """Fan out to every configured channel. Logs locally regardless."""
    log.info("ALERT: %s", message)

    sent_telegram = send_telegram(message)
    sent_discord = send_discord(message)
    sent_ntfy = send_ntfy(message)

    if not (sent_telegram or sent_discord or sent_ntfy):
        log.warning(
            "No notification channel is configured — alert was only logged. "
            "Set TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL, "
            "or NTFY_TOPIC."
        )
