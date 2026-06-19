"""Renders the brief into a clean HTML page (web-search-only data, rule-based guidance)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Template


_TEMPLATE = Template(
    r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Pre-Market Options Brief — {{ generated_et }}</title>
<style>
  :root {
    --bg: #0b0d10;
    --card: #14181d;
    --card2: #1a2028;
    --fg: #e6edf3;
    --muted: #8b96a3;
    --accent: #4ade80;
    --warn: #facc15;
    --bad: #f87171;
    --line: #2a323d;
  }
  * { box-sizing: border-box; }
  body {
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif;
    background: var(--bg);
    color: var(--fg);
    margin: 0;
    padding: 24px;
  }
  .wrap { max-width: 880px; margin: 0 auto; }
  header {
    margin-bottom: 18px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--line);
  }
  h1 { margin: 0 0 4px; font-size: 22px; }
  h2 { font-size: 16px; margin: 0 0 10px; letter-spacing: .02em; text-transform: uppercase; color: var(--muted); }
  .ts { color: var(--muted); font-size: 13px; }
  .grid { display: grid; gap: 14px; }
  .card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 16px 18px;
  }
  .row { display: flex; flex-wrap: wrap; gap: 12px; }
  .pill {
    display: inline-block; padding: 3px 9px; border-radius: 999px;
    font-size: 12px; font-weight: 600; letter-spacing: .03em;
    background: var(--card2); border: 1px solid var(--line); color: var(--fg);
  }
  .pill.trend { background: rgba(74,222,128,.12); color: var(--accent); border-color: rgba(74,222,128,.35); }
  .pill.chop  { background: rgba(248,113,113,.12); color: var(--bad);   border-color: rgba(248,113,113,.35); }
  .pill.mixed { background: rgba(250,204,21,.12);  color: var(--warn);  border-color: rgba(250,204,21,.35); }
  .pill.high  { background: rgba(248,113,113,.12); color: var(--bad);   border-color: rgba(248,113,113,.35); }
  .pill.medium{ background: rgba(250,204,21,.12);  color: var(--warn);  border-color: rgba(250,204,21,.35); }
  .pill.low   { background: rgba(74,222,128,.12);  color: var(--accent);border-color: rgba(74,222,128,.35); }
  ul { margin: 8px 0 0 18px; padding: 0; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); }
  th { color: var(--muted); font-weight: 600; }
  .kv { display: grid; grid-template-columns: 200px 1fr; gap: 8px 16px; }
  .kv .k { color: var(--muted); }
  .mono { font-family: ui-monospace, "SF Mono", Menlo, monospace; }
  .big { font-size: 18px; font-weight: 600; }
  .ok    { color: var(--accent); }
  .nope  { color: var(--bad); }
  .warn  { color: var(--warn); }
  .reminder {
    margin-top: 12px;
    background: rgba(250,204,21,.08);
    border: 1px dashed rgba(250,204,21,.35);
    color: var(--warn);
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 13px;
  }
  .footer { margin-top: 18px; color: var(--muted); font-size: 12px; text-align: center; }
  details summary { cursor: pointer; color: var(--muted); font-size: 13px; }
  pre { background: var(--card2); padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
</style>
</head>
<body>
<div class="wrap">

  <header>
    <h1>Pre-Market Options Brief</h1>
    <div class="ts">Generated {{ generated_et }} ET · Account ${{ "{:,.0f}".format(account_size) }} · Max risk {{ "{:.1f}".format(risk_pct * 100) }}%</div>
  </header>

  <div class="grid">

    <section class="card">
      <h2>Market Bias</h2>
      <div class="row" style="margin-bottom:8px;">
        <span class="pill {{ bias_class }}">{{ bias.read | upper | replace('_',' ') }}</span>
      </div>
      <div>{{ bias.summary }}</div>
      {% if bias.key_indicators %}
      <ul>
        {% for k in bias.key_indicators %}<li>{{ k }}</li>{% endfor %}
      </ul>
      {% endif %}
    </section>

    <section class="card">
      <h2>Premarket Read (web search)</h2>
      <div class="kv">
        <div class="k">ES futures</div><div>{{ premarket.futures.ES if premarket.futures else "—" }}</div>
        <div class="k">NQ futures</div><div>{{ premarket.futures.NQ if premarket.futures else "—" }}</div>
        <div class="k">SPY / QQQ</div><div>{{ premarket.spy_qqq or "—" }}</div>
        <div class="k">VIX</div><div>{{ premarket.vix.level }} — {{ premarket.vix.commentary }}</div>
      </div>
    </section>

    <section class="card">
      <h2>Today's Calendar</h2>
      {% if calendar.events %}
      <table>
        <thead><tr><th>Time (ET)</th><th>Event</th><th>Impact</th></tr></thead>
        <tbody>
        {% for e in calendar.events %}
          <tr>
            <td class="mono">{{ e.time_et }}</td>
            <td>{{ e.event }}</td>
            <td><span class="pill {{ e.impact }}">{{ e.impact | upper }}</span></td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
      {% else %}<div class="ts">No major events flagged.</div>{% endif %}
      {% if calendar.summary %}<p style="margin-top:8px;">{{ calendar.summary }}</p>{% endif %}
    </section>

    <section class="card">
      <h2>Overnight / Premarket News</h2>
      {% if news.headlines %}
      <ul>
        {% for h in news.headlines %}<li>{{ h }}</li>{% endfor %}
      </ul>
      {% endif %}
      {% if news.market_movers %}<p style="margin-top:8px;">{{ news.market_movers }}</p>{% endif %}
    </section>

    <section class="card">
      <h2>Recommended Setup</h2>
      <div class="row" style="margin-bottom:8px;">
        <span class="pill">{{ recommended_setup.name | replace('_',' ') }}</span>
        <span class="pill {{ recommended_setup.confidence }}">{{ recommended_setup.confidence | upper }} CONFIDENCE</span>
      </div>
      <div>{{ recommended_setup.rationale }}</div>
    </section>

    {% if guidance.ticker %}
    <section class="card">
      <h2>Trade Guidance</h2>
      <div class="kv">
        <div class="k">Ticker</div><div class="mono big">{{ guidance.ticker }} {{ guidance.direction | upper }}</div>
        <div class="k">Strike rule</div><div>{{ guidance.strike_rule }}</div>
        <div class="k">Target expiration</div><div class="mono">{{ target_expiration or "—" }} ({{ guidance.dte_target }} biz days)</div>
        <div class="k">Why this ticker</div><div>{{ guidance.ticker_rationale }}</div>
      </div>

      <div style="margin-top:12px;">
        <h2 style="margin-top:0;">Key Levels</h2>
        <div class="kv">
          <div class="k">Support</div><div class="mono">{{ key_levels.support | join(', ') if key_levels.support else "—" }}</div>
          <div class="k">Resistance</div><div class="mono">{{ key_levels.resistance | join(', ') if key_levels.resistance else "—" }}</div>
        </div>
        {% if key_levels.notes %}<p style="margin-top:8px;">{{ key_levels.notes }}</p>{% endif %}
      </div>

      <div style="margin-top:12px;">
        <h2 style="margin-top:0;">Entry / Exit</h2>
        <div class="kv">
          <div class="k">Entry trigger</div><div>{{ entry_trigger }}</div>
          <div class="k">Exit rule</div><div>{{ exit_rule }}</div>
        </div>
      </div>

      <div class="reminder">
        Confirm in your broker before placing the trade: pull the live chain for {{ guidance.ticker }} at the closest available expiration to {{ target_expiration }}, apply the strike rule above, then size contracts as floor(${{ "{:,.0f}".format(max_risk_dollars) }} / (mid_premium × 100)) so total cost stays inside your {{ "{:.1f}".format(risk_pct * 100) }}% risk budget.
      </div>
    </section>
    {% else %}
    <section class="card">
      <h2>Trade Guidance</h2>
      <p>Sit out today — no high-confidence mechanical setup. Stand aside and preserve capital.</p>
    </section>
    {% endif %}

    <section class="card">
      <h2>Wheel / Premium Check</h2>
      <div class="row" style="margin-bottom:8px;">
        <span class="pill {{ 'low' if wheel_check.good_for_csp else 'high' }}">
          {{ "OK FOR NEW CSPs" if wheel_check.good_for_csp else "AVOID NEW CSPs TODAY" }}
        </span>
      </div>
      <div>{{ wheel_check.rationale }}</div>
    </section>

    <section class="card">
      <h2>Risk Reminder</h2>
      <div>{{ risk_reminder }}</div>
    </section>

    <details class="card">
      <summary>Raw brief (debug)</summary>
      <pre>{{ raw_json }}</pre>
    </details>

  </div>

  <div class="footer">
    Generated automatically · Data via Claude + web search · Not financial advice · Verify all data before trading.
  </div>
</div>
</body>
</html>
"""
)


def render_html(
    *,
    brief: dict[str, Any],
    target_expiration: str | None,
    account_size: float,
    risk_pct: float,
    generated_et: str,
    raw_json: str,
) -> str:
    bias = brief.get("market_bias", {})
    bias_read = (bias.get("read") or "mixed").lower()
    bias_class = {"trend_day": "trend", "chop_day": "chop", "mixed": "mixed"}.get(
        bias_read, "mixed"
    )

    premarket = brief.get(
        "premarket_data",
        {"futures": {"ES": "", "NQ": ""}, "spy_qqq": "", "vix": {"level": "", "commentary": ""}},
    )

    return _TEMPLATE.render(
        generated_et=generated_et,
        account_size=account_size,
        risk_pct=risk_pct,
        max_risk_dollars=account_size * risk_pct,
        bias=bias,
        bias_class=bias_class,
        premarket=premarket,
        calendar=brief.get("calendar", {"events": [], "summary": ""}),
        news=brief.get("news", {"headlines": [], "market_movers": ""}),
        recommended_setup=brief.get(
            "recommended_setup", {"name": "SIT_OUT", "rationale": "", "confidence": "low"}
        ),
        guidance=brief.get(
            "trade_guidance",
            {"ticker": "", "direction": "", "strike_rule": "", "dte_target": 0, "ticker_rationale": ""},
        ),
        target_expiration=target_expiration,
        key_levels=brief.get("key_levels", {"support": [], "resistance": [], "notes": ""}),
        entry_trigger=brief.get("entry_trigger", "—"),
        exit_rule=brief.get("exit_rule", "—"),
        wheel_check=brief.get(
            "wheel_check", {"good_for_csp": False, "rationale": "—"}
        ),
        risk_reminder=brief.get("risk_reminder", "—"),
        raw_json=raw_json,
    )


def now_et_str() -> str:
    """Render current ET timestamp like 'Thu Jun 18 2026 08:45 AM'."""
    import pytz

    et = pytz.timezone("America/New_York")
    return datetime.now(et).strftime("%a %b %d %Y %I:%M %p")
