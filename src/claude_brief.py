"""Calls Anthropic Claude with the web_search tool to produce the entire daily brief.

Web search is the SINGLE data source. Claude is responsible for pulling:
  - Overnight ES/NQ futures direction
  - Premarket SPY/QQQ price action and sentiment
  - VIX level and volatility commentary
  - Today's economic calendar (Fed events, major data)
  - Significant overnight news that could move markets

And then synthesizing into:
  - Market bias (trend day vs chop day)
  - One of the 7 setups (or SIT_OUT)
  - A single ticker from the watchlist
  - Direction (call/put) for momentum setups
  - Strike RULE (not an exact strike) — e.g. "ATM or 1 OTM", "~0.30 delta"
  - DTE target — an integer number of trading days (Python converts to a date)
  - Key levels, entry trigger, exit rule
  - Wheel/CSP check
  - Risk reminder

The user looks up the live chain in their broker each morning to apply the rule.
"""

from __future__ import annotations

import json
import re
from typing import Any

from anthropic import Anthropic


VALID_SETUPS = {
    "ORB",
    "EMA_PULLBACK",
    "VWAP",
    "TIME_WINDOWS",
    "GAP_FILL",
    "FCHOD",
    "MTF_CONFLUENCE",
    "SIT_OUT",
}


def _build_prompt(
    *,
    today_str: str,
    watchlist: list[str],
    enabled_setups: list[str],
    setup_rules: dict[str, Any],
    account_size: float,
    risk_pct: float,
    csp_target_delta: float,
    vix_min_for_premium: float,
) -> str:
    return f"""You are an experienced day-trader's pre-market analyst. Today is {today_str}.

ACCOUNT CONTEXT
- Account size: ${account_size:,.0f}
- Max risk per trade: {risk_pct * 100:.1f}%
- Watchlist (pick from these or another highly-liquid US large-cap if a clear catalyst justifies it): {", ".join(watchlist)}

THE 7 MECHANICAL SETUPS YOU CAN RECOMMEND (or SIT_OUT if conditions are bad):
{json.dumps(setup_rules, indent=2)}

Enabled setups: {", ".join(enabled_setups)}

YOUR DATA-GATHERING TASKS — USE web_search FOR ALL OF THESE
1. Overnight ES and NQ futures direction (point change, %, key overnight high/low if notable).
2. Premarket SPY and QQQ price action and general sentiment.
3. Current VIX level and any notable volatility commentary.
4. Today's US economic calendar in ET (Fed speakers, FOMC, CPI/PPI/NFP/PCE/ISM/Jobless Claims/Retail Sales/etc.). Include time, event, and impact level.
5. Significant overnight + premarket news that could move markets today (single-stock catalysts on watchlist names, geopolitics, earnings reactions, central-bank news).

YOUR ANALYSIS TASKS
6. Read all of the above and form a market bias: trend day vs. chop day. Consider VIX level, futures direction, gap size, news catalysts, calendar event risk.
7. Pick ONE of the 7 setups that best fits today's conditions, OR return SIT_OUT if it's a clear chop / no-edge day (e.g. FOMC day with no clear pre-event setup, very low ES range overnight, conflicting catalysts).
8. Pick the single ticker from the watchlist (or another liquid name with a real catalyst) that has the cleanest match for the chosen setup.
9. Pick a direction (call or put) consistent with the setup and bias.
10. State the strike rule that applies for the chosen setup (do NOT pick a specific strike — the user looks that up in their broker):
    - Momentum/breakout (ORB, EMA_PULLBACK, VWAP, FCHOD, GAP_FILL): "ATM or 1 strike OTM"
    - MTF_CONFLUENCE: "Slightly more OTM acceptable for leverage (~1-2 strikes OTM)"
    - Wheel/CSP days: "~{csp_target_delta:.2f} delta"
11. State the DTE target as an INTEGER number of trading days (the Python code will convert to a calendar date):
    - Use the rule from the setup definition above for the chosen ticker class (SPY/QQQ vs stocks).
    - For DTE ranges like [2, 5], pick a single representative integer in the range (typically the lower end for momentum, middle for swing).
    - For "ALL: 0" rules, return 0.
12. Define key levels (support/resistance), a specific entry trigger, and a specific exit rule.
13. Decide whether today is good for opening NEW cash-secured puts: yes if VIX >= {vix_min_for_premium} AND no high-impact event risk in next 1-2 days. Target ~{csp_target_delta:.2f} delta.
14. Give a 1-line risk reminder grounded in the account size + risk %.

OUTPUT FORMAT (STRICT)
Return ONLY a single JSON object with this exact schema. No prose before or after. No markdown. Just JSON.

{{
  "premarket_data": {{
    "futures": {{
      "ES": "e.g. +12.5 pts (+0.22%) overnight; held above 5520",
      "NQ": "e.g. +45 pts (+0.21%); steady through Asia"
    }},
    "spy_qqq": "1-2 sentences on premarket SPY and QQQ action and sentiment",
    "vix": {{
      "level": "e.g. 14.2",
      "commentary": "1 sentence on volatility regime"
    }}
  }},
  "market_bias": {{
    "read": "trend_day" | "chop_day" | "mixed",
    "summary": "2-3 sentences explaining the read",
    "key_indicators": ["bullet 1", "bullet 2", "bullet 3"]
  }},
  "calendar": {{
    "events": [
      {{"time_et": "HH:MM AM/PM", "event": "name", "impact": "high|medium|low"}}
    ],
    "summary": "1 sentence on whether calendar drives today's action"
  }},
  "news": {{
    "headlines": ["headline 1", "headline 2", "headline 3"],
    "market_movers": "1-2 sentences on the most market-moving items"
  }},
  "recommended_setup": {{
    "name": "ORB" | "EMA_PULLBACK" | "VWAP" | "TIME_WINDOWS" | "GAP_FILL" | "FCHOD" | "MTF_CONFLUENCE" | "SIT_OUT",
    "rationale": "2-3 sentences on WHY this setup fits today",
    "confidence": "low" | "medium" | "high"
  }},
  "trade_guidance": {{
    "ticker": "SPY",
    "direction": "call" | "put",
    "strike_rule": "ATM or 1 strike OTM",
    "dte_target": 1,
    "ticker_rationale": "1-2 sentences on why this ticker for this setup today"
  }},
  "key_levels": {{
    "support": [550.20, 548.50],
    "resistance": [553.80, 555.00],
    "notes": "1 sentence on which level matters most"
  }},
  "entry_trigger": "Specific, mechanical condition to enter (e.g. 'Break and hold above 553.80 on 5min close after 9:45 AM ET')",
  "exit_rule": "Specific stop and target (e.g. 'Stop at 552.50 (1R), target 555.50 / VWAP rejection')",
  "wheel_check": {{
    "good_for_csp": true,
    "rationale": "1-2 sentences on IV/VIX environment and event risk"
  }},
  "risk_reminder": "1 sentence using ${account_size:,.0f} and {risk_pct * 100:.1f}% risk"
}}

If recommended_setup.name is SIT_OUT, set trade_guidance.ticker to "", trade_guidance.direction to "", trade_guidance.strike_rule to "", trade_guidance.dte_target to 0, and key_levels arrays to []. Still fill in premarket_data, market_bias, calendar, news, wheel_check, and risk_reminder.
"""


def _extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of Claude's text response, tolerant to fences/extra prose."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError(f"No JSON object found in Claude response: {text[:500]}")


def _stringify_text_blocks(content: list[Any]) -> str:
    """Concatenate all 'text' content blocks from an Anthropic Message."""
    parts: list[str] = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            parts.append(getattr(block, "text", "") or "")
    return "\n".join(parts).strip()


def generate_brief(
    *,
    api_key: str,
    model: str,
    max_tokens: int,
    today_str: str,
    watchlist: list[str],
    enabled_setups: list[str],
    setup_rules: dict[str, Any],
    account_size: float,
    risk_pct: float,
    csp_target_delta: float,
    vix_min_for_premium: float,
) -> dict[str, Any]:
    """Returns the parsed JSON brief from Claude. Raises on failure."""
    client = Anthropic(api_key=api_key)
    prompt = _build_prompt(
        today_str=today_str,
        watchlist=watchlist,
        enabled_setups=enabled_setups,
        setup_rules=setup_rules,
        account_size=account_size,
        risk_pct=risk_pct,
        csp_target_delta=csp_target_delta,
        vix_min_for_premium=vix_min_for_premium,
    )

    web_search_tool = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 8,
    }

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        tools=[web_search_tool],
        messages=[{"role": "user", "content": prompt}],
    )

    text = _stringify_text_blocks(message.content)
    brief = _extract_json(text)

    setup_name = brief.get("recommended_setup", {}).get("name")
    if setup_name not in VALID_SETUPS:
        raise ValueError(f"Claude returned invalid setup: {setup_name!r}")

    return brief
