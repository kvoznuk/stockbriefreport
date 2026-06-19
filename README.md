# Stock Brief Report

Automated daily pre-market options brief. Every weekday at ~8:45am ET, a GitHub Actions workflow:

1. Calls Claude (Anthropic) with the `web_search` tool. Claude pulls **all** market data — overnight ES/NQ futures, premarket SPY/QQQ price action, VIX level, today's economic calendar, and overnight news.
2. Synthesizes the data into a market bias read (trend day vs. chop day) and picks one of your 7 mechanical setups (or "sit out today").
3. Outputs trade **guidance** — ticker, direction, strike rule (e.g. "ATM or 1 OTM" or "~0.30 delta"), and a target expiration date — not a specific contract. You confirm strike/premium/contract count in your own broker each morning.
4. Writes a clean HTML page to `docs/index.html`, served by GitHub Pages.
5. Sends a short SMS summary to your phone via T-Mobile's email-to-SMS gateway.

## Architecture

| Layer | What |
|---|---|
| Language | Python 3.11+ |
| Scheduler | GitHub Actions cron (`.github/workflows/daily-brief.yml`) |
| Hosting | GitHub Pages (the same repo, `/docs` folder) |
| **Data source** | **Anthropic Claude with `web_search_20250305` tool — single source for futures, premarket, VIX, calendar, news** |
| LLM | Anthropic Claude (`claude-sonnet-4-5` by default) |
| SMS | Gmail SMTP → `2403291689@tmomail.net` |

No options chain API, no brokerage API, no market data API. Just Anthropic + Gmail.

## Project layout

```
.
├── .github/workflows/daily-brief.yml   GH Actions cron + Pages deploy
├── config.yaml                          your fixed parameters (account, risk, watchlist, setup rules)
├── docs/                                served by GitHub Pages
│   ├── index.html                       overwritten each morning
│   └── archive/YYYY-MM-DD.html          one snapshot per day
├── requirements.txt
├── src/
│   ├── main.py                          orchestrator (ET window guard + DTE -> date math)
│   ├── config.py                        loads config.yaml + env
│   ├── claude_brief.py                  Anthropic call with web_search
│   ├── html_renderer.py                 Jinja2 -> HTML
│   └── sms.py                           Gmail SMTP -> tmomail.net
└── README.md
```

---

## One-time setup (~10 minutes, do this once)

### 1. Get an Anthropic API key

- Go to <https://console.anthropic.com>.
- Settings → API Keys → Create Key. Copy the `sk-ant-…` value.
- Billing → add ~$5 of credit.

### 2. Create a Gmail App Password

Gmail will not let SMTP log in with your normal password. You need an **App Password**:

1. Go to <https://myaccount.google.com/security>.
2. Turn on **2-Step Verification** if you haven't already.
3. Go to <https://myaccount.google.com/apppasswords>.
4. Choose app: "Mail", device: "Other (custom name)" → name it "StockBriefReport" → **Generate**.
5. Copy the 16-character password (shown without spaces). Save it.

### 3. Create the GitHub repo + push

```bash
cd /Users/kamilla/StockBriefReport
git commit -m "Initial scaffold"
gh repo create StockBriefReport --public --source=. --push   # if you have gh CLI
# OR create the repo on github.com manually and:
# git remote add origin git@github.com:<you>/StockBriefReport.git
# git push -u origin main
```

(The repo is already `git init`'d and staged from the scaffold step — just commit and push.)

### 4. Add the secrets to GitHub

Repo on github.com → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**. Add these three:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from step 1 |
| `GMAIL_USER`        | your full Gmail address, e.g. `you@gmail.com` |
| `GMAIL_APP_PASSWORD`| 16-char value from step 2 |

Then add one **repository variable** (Settings → Secrets and variables → Actions → Variables tab → New repository variable):

| Name | Value |
|---|---|
| `PUBLIC_BRIEF_URL` | `https://<your-github-username>.github.io/StockBriefReport/` |

### 5. Enable GitHub Pages

Repo → **Settings** → **Pages**:

- Source: **Deploy from a branch**
- Branch: **`main`** / folder: **`/docs`**
- Save. After ~30 seconds your site is live at `https://<you>.github.io/StockBriefReport/`.

### 6. Trigger the first run manually

Repo → **Actions** → **Daily Pre-Market Brief** → **Run workflow** → leave `force=true` → **Run**.

This bypasses the "8:30-9:00am ET only" guard so you can verify the full pipeline end-to-end on demand. Within ~1-2 minutes:

- `docs/index.html` gets overwritten on `main`
- GH Pages republishes (~30s)
- You receive an SMS

Bookmark the Pages URL. You're done.

---

## What's automated after that

Every weekday at ~8:45am ET, the workflow fires automatically (no laptop required, no manual step). The `docs/index.html` is overwritten in place; your bookmark always shows today's brief. Every prior day is preserved under `docs/archive/YYYY-MM-DD.html`.

Two cron entries are in the workflow (`12:45 UTC` and `13:45 UTC`) so the brief lands at 8:45am ET regardless of EDT/EST. The Python script's ET time-window guard ensures only the correct trigger actually does work — the wrong-side trigger no-ops.

---

## Local testing

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env with your real keys
set -a; source .env; set +a

python -m src.main --force --no-sms      # run, skip SMS
open docs/index.html                      # preview
```

---

## Configuration reference (`config.yaml`)

| Key | Default | What it does |
|---|---|---|
| `account.size_usd` | 25000 | Used for risk-dollar math + risk reminder copy |
| `account.max_risk_per_trade_pct` | 1.0 | Caps the total risk budget the brief reminds you of |
| `watchlist.primary` | `[SPY, QQQ]` | Your core watchlist |
| `watchlist.expanded` | `[SPY,QQQ,AAPL,NVDA,...]` | Claude can pick from this broader list when a real catalyst justifies it |
| `setups.enabled` | all 7 | If you want to filter to a subset later, edit this list |
| `setups.rules.<NAME>` | per-spec | DTE windows + strike rule per setup |
| `wheel.csp_target_delta` | 0.30 | Target delta for premium-selling days |
| `wheel.vix_min_for_premium_selling` | 18 | Heuristic Claude uses to gate "good for new CSPs" |
| `claude.model` | `claude-sonnet-4-5` | Anthropic model id (change here if you have access to a newer one) |
| `sms.to` | `2403291689@tmomail.net` | T-Mobile email-to-SMS gateway |
| `sms.max_chars` | 300 | Hard cap on SMS body length |

---

## How the trade guidance is structured

Claude outputs:

- **Ticker** — chosen from your watchlist (or another liquid name if a clear catalyst justifies it).
- **Direction** — call or put.
- **Strike rule** — e.g. "ATM or 1 strike OTM" for momentum setups, "~0.30 delta" for wheel/CSP days, "slightly more OTM (~1-2 strikes)" for MTF confluence. **Not a specific strike** — you look up the live chain in your broker.
- **DTE target** — an integer number of business days. Python converts this to a target calendar date so the brief shows e.g. "Target expiration: 2026-06-19 (1 biz days)".

The brief includes a yellow reminder box: confirm the closest available expiration in your broker, apply the strike rule, then size contracts so total cost ≤ `account_size × risk_pct`. The math is `floor(max_risk_dollars / (mid_premium × 100))` once you see the live mid premium.

---

## Troubleshooting

- **Workflow runs but no commit:** the ET time-window guard skipped this run (e.g. wrong DST trigger). Check the workflow log; this is by design.
- **Claude returns invalid JSON:** the orchestrator raises and the workflow fails. Re-run; Claude is usually deterministic enough that this is rare. If persistent, lower `claude.max_tokens` or simplify the prompt.
- **SMS not arriving:** verify Gmail App Password (not your real password). Check workflow log for SMTP errors.
- **Pages 404:** GitHub Pages takes ~30s after first commit. Confirm Settings → Pages source is `main` / `/docs`.

---

## Disclaimer

This tool is decision support, not financial advice. Verify all data and exercise your own judgment before placing any trade.
