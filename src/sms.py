"""Send a short SMS summary via Gmail SMTP -> T-Mobile email-to-SMS gateway.

Gmail SMTP requires an "App password" — not your Google account password.
See README for setup. Env vars:
  GMAIL_USER             your full Gmail address
  GMAIL_APP_PASSWORD     16-char app password from myaccount.google.com
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage


def build_summary(
    *,
    bias_read: str,
    setup_name: str,
    ticker: str,
    direction: str,
    public_url: str,
    max_chars: int = 300,
) -> str:
    """Build a 1-2 sentence summary that fits in `max_chars`.

    Pattern: '<BIAS>. Setup: <SETUP> on <TICKER> <DIR>. <URL>'
    Example: 'TREND DAY. Setup: ORB on SPY CALL. https://...'
    """
    bias = (bias_read or "mixed").replace("_", " ").upper()
    setup = (setup_name or "SIT_OUT").replace("_", " ")
    if setup_name == "SIT_OUT" or not ticker:
        head = f"{bias}. Setup: SIT OUT today."
    else:
        head = f"{bias}. Setup: {setup} on {ticker} {direction.upper()}."

    full = f"{head} {public_url}".strip()
    if len(full) <= max_chars:
        return full

    overflow = len(full) - max_chars
    head_trim = max(0, len(head) - overflow - 1)
    head_short = head[:head_trim].rstrip(" .,") + "."
    return f"{head_short} {public_url}".strip()


def send_sms_via_gmail(
    *,
    gmail_user: str,
    gmail_app_password: str,
    to_address: str,
    body: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = ""
    msg["From"] = gmail_user
    msg["To"] = to_address
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
        s.login(gmail_user, gmail_app_password)
        s.send_message(msg)
