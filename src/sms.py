"""Send a short SMS summary via Gmail SMTP -> T-Mobile email-to-SMS gateway.

Gmail SMTP requires an "App password" — not your Google account password.
See README for setup. Env vars:
  GMAIL_USER             your full Gmail address
  GMAIL_APP_PASSWORD     16-char app password from myaccount.google.com
"""

from __future__ import annotations

import smtplib
import unicodedata
from email.message import EmailMessage


def _to_sms_ascii(text: str) -> str:
    """Make text SMS-safe: convert fancy quotes/dashes to ASCII, replace
    non-breaking spaces, then drop any remaining non-ASCII chars.

    Carrier email-to-SMS gateways often choke on non-ASCII (esp. \\xa0 which
    can sneak in via clipboard pastes), and SMS itself is GSM 7-bit anyway."""
    text = text.replace("\xa0", " ")
    text = unicodedata.normalize("NFKD", text)
    return text.encode("ascii", "ignore").decode("ascii")


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

    full = _to_sms_ascii(f"{head} {public_url}".strip())
    if len(full) <= max_chars:
        return full

    overflow = len(full) - max_chars
    head_trim = max(0, len(head) - overflow - 1)
    head_short = head[:head_trim].rstrip(" .,") + "."
    return _to_sms_ascii(f"{head_short} {public_url}".strip())


def send_sms_via_gmail(
    *,
    gmail_user: str,
    gmail_app_password: str,
    to_address: str,
    body: str,
) -> None:
    safe_user = _to_sms_ascii(gmail_user)
    safe_to = _to_sms_ascii(to_address)
    safe_body = _to_sms_ascii(body)
    # Google displays app passwords with visual spaces (e.g. "abcd efgh ijkl mnop").
    # Copy-paste sometimes turns those into \xa0 (non-breaking space). Strip any
    # whitespace + non-ASCII so the SASL auth string is pure ASCII alphanumerics.
    safe_password = "".join(
        c for c in gmail_app_password if c.isascii() and not c.isspace()
    )

    print(
        f"[sms-debug] from={safe_user!r} to={safe_to!r} body_len={len(safe_body)} "
        f"pwd_len={len(safe_password)} body_preview={safe_body[:80]!r}"
    )

    msg = EmailMessage()
    msg["Subject"] = ""
    msg["From"] = safe_user
    msg["To"] = safe_to
    msg.set_content(safe_body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
        s.login(safe_user, safe_password)
        s.send_message(msg)
