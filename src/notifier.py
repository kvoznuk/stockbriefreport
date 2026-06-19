"""Send the daily brief summary via Telegram Bot API.

Setup (one-time, ~5 minutes):
  1. In Telegram, search for @BotFather and start a chat.
  2. Send /newbot, follow the prompts. Pick a display name and a unique
     username ending in 'bot' (e.g. kvoznuk_brief_bot).
  3. BotFather replies with an HTTP API token like
     '1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ012345678'. That's TELEGRAM_BOT_TOKEN.
  4. In Telegram, search for your bot's username and send it any message
     (e.g. /start). This creates a chat with you.
  5. Open https://api.telegram.org/bot<TOKEN>/getUpdates in a browser
     (replace <TOKEN>). You'll see JSON; find result[0].message.chat.id.
     That number is TELEGRAM_CHAT_ID.

  Add both as GitHub repo secrets and you're done.

Telegram supports up to 4096 chars per message and Markdown formatting.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request


TELEGRAM_API_BASE = "https://api.telegram.org"


def build_summary(
    *,
    bias_read: str,
    setup_name: str,
    ticker: str,
    direction: str,
    public_url: str,
    strike_rule: str = "",
    target_expiration: str | None = None,
) -> str:
    """Build a 2-4 line Telegram summary. Uses Markdown for emphasis."""
    bias = (bias_read or "mixed").replace("_", " ").upper()
    setup = (setup_name or "SIT_OUT").replace("_", " ")

    if setup_name == "SIT_OUT" or not ticker:
        return (
            f"*{bias}* — sit out today.\n"
            f"[Open full brief]({public_url})"
        ).strip()

    lines = [f"*{bias}* — {setup} on `{ticker} {direction.upper()}`"]
    if strike_rule:
        lines.append(f"Strike: {strike_rule}")
    if target_expiration:
        lines.append(f"Target exp: `{target_expiration}`")
    lines.append(f"[Open full brief]({public_url})")
    return "\n".join(lines)


def send_telegram(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
) -> dict:
    """POST to Telegram Bot API. Raises on non-200 or API error."""
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "false",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        result = json.loads(body)

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result.get('description', 'unknown')} "
            f"(error_code={result.get('error_code')})"
        )
    return result
