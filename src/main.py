"""Daily pre-market brief orchestrator (web-search-only data).

Flow:
  1. Guard: only run inside the 8:30am-9:00am ET window (skip on weekends/holidays
     by virtue of GH Actions cron set to Mon-Fri).
  2. Call Claude with the web_search tool — Claude pulls ALL market data
     (futures, premarket, VIX, calendar, news) and synthesizes the brief
     including a strike RULE and DTE target.
  3. Convert DTE target -> calendar date via business-day arithmetic.
  4. Render the merged HTML, write to docs/index.html (and archive a dated copy).
  5. Send SMS summary via Gmail -> 2403291689@tmomail.net.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytz

from .claude_brief import generate_brief
from .config import load_config, optional_env, require_env
from .html_renderer import now_et_str, render_html
from .sms import build_summary, send_sms_via_gmail


def _et_now() -> datetime:
    return datetime.now(pytz.timezone("America/New_York"))


def _within_run_window(force: bool) -> bool:
    """Only run if it's currently 8:30am-9:00am ET (or --force).

    GH Actions cron uses UTC, so we schedule at both 12:45 and 13:45 UTC to cover
    EDT and EST. This guard filters out the off-DST trigger.
    """
    if force:
        return True
    now = _et_now()
    if now.weekday() >= 5:
        return False
    return (now.hour == 8 and now.minute >= 30) or (now.hour == 9 and now.minute == 0)


def _archive_path(archive_dir: str) -> Path:
    et = _et_now()
    p = Path(archive_dir) / f"{et.strftime('%Y-%m-%d')}.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def add_business_days(start: date, n: int) -> date:
    """Add `n` business days (Mon-Fri) to `start`. n=0 returns `start`.

    Approximation: ignores US market holidays. The brief instructs the user
    to confirm the closest available expiration in their broker, so a
    holiday-shifted date is fine — they'll pick the nearest weekly anyway.
    """
    if n <= 0:
        return start
    d = start
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily pre-market options brief.")
    parser.add_argument("--force", action="store_true", help="Skip the ET time-window guard.")
    parser.add_argument("--no-sms", action="store_true", help="Skip the SMS step.")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config.yaml (default: ./config.yaml)"
    )
    args = parser.parse_args()

    if not _within_run_window(args.force):
        et = _et_now().strftime("%a %Y-%m-%d %H:%M ET")
        print(f"[skip] Outside run window ({et}). Use --force to override.")
        return 0

    cfg = load_config(args.config)

    print("[1/4] Calling Claude with web_search for the daily brief…")
    anthropic_key = require_env("ANTHROPIC_API_KEY")
    today_et = _et_now()
    today_str = today_et.strftime("%A, %B %d, %Y")
    brief = generate_brief(
        api_key=anthropic_key,
        model=cfg.claude_model,
        max_tokens=cfg.claude_max_tokens,
        today_str=today_str,
        watchlist=cfg.expanded_watchlist,
        enabled_setups=cfg.enabled_setups,
        setup_rules=cfg.setup_rules,
        account_size=cfg.account_size,
        risk_pct=cfg.max_risk_pct,
        csp_target_delta=cfg.csp_target_delta,
        vix_min_for_premium=cfg.vix_min_for_premium,
    )
    print("[1/4] Claude brief received.")
    print(json.dumps(brief, indent=2)[:1500])

    setup_name = brief["recommended_setup"]["name"]
    guidance = brief.get("trade_guidance", {}) or {}
    ticker = (guidance.get("ticker") or "").upper().strip()
    direction = (guidance.get("direction") or "").lower().strip()
    strike_rule = (guidance.get("strike_rule") or "").strip()
    dte_target = guidance.get("dte_target")

    target_expiration: str | None = None
    if setup_name != "SIT_OUT" and ticker and isinstance(dte_target, int) and dte_target >= 0:
        target_expiration = add_business_days(today_et.date(), dte_target).isoformat()
        print(f"[2/4] Target expiration: {target_expiration} ({dte_target} business days from today)")
    else:
        print("[2/4] No trade guidance (SIT_OUT or incomplete picks).")

    print("[3/4] Rendering HTML…")
    raw_json = json.dumps(brief, indent=2)
    html = render_html(
        brief=brief,
        target_expiration=target_expiration,
        account_size=cfg.account_size,
        risk_pct=cfg.max_risk_pct,
        generated_et=now_et_str(),
        raw_json=raw_json,
    )

    out_path = Path(cfg.html_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[3/4] Wrote {out_path}")

    archive = _archive_path(cfg.archive_dir)
    archive.write_text(html, encoding="utf-8")
    print(f"[3/4] Archived to {archive}")

    if args.no_sms:
        print("[4/4] SMS skipped (--no-sms).")
        return 0

    public_url = optional_env("PUBLIC_BRIEF_URL", "")
    sms_body = build_summary(
        bias_read=brief.get("market_bias", {}).get("read", "mixed"),
        setup_name=setup_name,
        ticker=ticker,
        direction=direction,
        public_url=public_url or "(brief published)",
        max_chars=cfg.sms_max_chars,
    )
    print(f"[4/4] SMS body ({len(sms_body)} chars): {sms_body}")

    gmail_user = os.environ.get("GMAIL_USER")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_app_password:
        print("[warn] GMAIL_USER / GMAIL_APP_PASSWORD not set; skipping SMS send.")
        return 0

    try:
        send_sms_via_gmail(
            gmail_user=gmail_user,
            gmail_app_password=gmail_app_password,
            to_address=cfg.sms_to,
            body=sms_body,
        )
        print(f"[4/4] SMS sent to {cfg.sms_to}")
    except Exception as e:
        print(f"[warn] SMS send failed: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
