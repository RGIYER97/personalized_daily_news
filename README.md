# Daily News & Sports Briefing

A Python-based daily news and sports aggregator that runs every morning via GitHub Actions, synthesizes headlines with an LLM, and delivers a briefing via SMS or email — all using free services.

Repository: [RGIYER97/personalized_daily_news](https://github.com/RGIYER97/personalized_daily_news)

## Features

- **News synthesizer** — Pulls headlines from NewsAPI (with RSS + Google News fallback) across four categories: Economic & Financial, Geopolitics, General News, and Technology. Google Gemini turns raw headlines into **blunt, factual summaries** (not a list of article titles).
- **Two-pass quality loop** — Pass 1 summarizes what happened and why it matters; pass 2 checks for clickbait or title dumping and rewrites if needed.
- **Stock watchlist** — One line per ticker for meaningful company news (earnings, deals, lawsuits, notable moves). Tick list is editable in `config.py`. If nothing notable turned up, the briefing says so.
- **Sports desk** — ESPN for yesterday's results and today's schedule: Oakland Athletics, New York Mets, Las Vegas Raiders, Sacramento Kings, Los Angeles Lakers, Real Madrid, Formula 1.
- **Free SMS** — Email-to-SMS carrier gateways (no Twilio). Falls back to full email if the message is too long.
- **GitHub Actions** — Scheduled daily run; no always-on laptop required.

## Briefing order

Each run outputs: **Header → News → Stocks → Sports → footer.**

## Project structure

```
main.py                              — Orchestrator and scheduler
news_fetcher.py                      — News + stock headlines, Gemini synthesis
sports_fetcher.py                   — ESPN scores and schedules
notifier.py                          — SMS gateway + SMTP email
config.py                            — Topics, watchlist, sports teams (.env for secrets)
.env.example                         — Environment template
.github/workflows/daily-briefing.yml — Cron + manual dispatch
```

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Purpose | Notes |
|---|---|---|
| `NEWSAPI_KEY` | [NewsAPI](https://newsapi.org) | Free tier; improves headline quality vs RSS-only |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | **Strongly recommended** — without it, news and stocks are mostly raw headlines |
| `USER_PHONE` | 10-digit US number | e.g. `2125551234` |
| `USER_CARRIER` | Carrier slug | See table below (`tmobile`, `verizon`, …) |
| `USER_EMAIL` | Your inbox | Email fallback recipient |
| `SMTP_EMAIL` | Gmail used to send | Often same as `USER_EMAIL` |
| `SMTP_PASSWORD` | [Gmail App Password](https://myaccount.google.com/apppasswords) | Not your normal Gmail login password |
| `SMTP_HOST` / `SMTP_PORT` | Usually `smtp.gmail.com` / `587` | |

### Supported carriers (Email-to-SMS)

| Carrier | `USER_CARRIER` |
|---|---|
| AT&T | `att` |
| T-Mobile | `tmobile` |
| Verizon | `verizon` |
| Sprint | `sprint` |
| US Cellular | `uscellular` |
| Boost Mobile | `boost` |
| Cricket | `cricket` |
| Metro by T-Mobile | `metro` |
| Mint Mobile | `mint` |
| Google Fi | `googlefi` |
| Xfinity Mobile | `xfinity` |
| Visible | `visible` |

### 3. Test locally

```bash
python main.py --now
```

## GitHub Actions (recommended)

Uses ~1 minute per run; fits the free Actions allowance.

### Use this repo

If you use [personalized_daily_news](https://github.com/RGIYER97/personalized_daily_news), fork or clone it, then add **Settings → Secrets and variables → Actions** repository secrets:

| Secret | Value |
|---|---|
| `NEWSAPI_KEY` | NewsAPI key |
| `GEMINI_API_KEY` | Gemini key (needed for good summaries) |
| `USER_PHONE` | 10-digit number |
| `USER_CARRIER` | e.g. `tmobile` |
| `USER_EMAIL` | Your email |
| `SMTP_EMAIL` | Gmail sender |
| `SMTP_PASSWORD` | Gmail App Password |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |

### Verify

1. **Actions** → **Daily News Briefing** → **Run workflow**
2. Confirm SMS or email arrives

### Schedule (UTC)

The workflow uses cron in UTC. Example: `0 12 * * *` ≈ 7:00 AM Eastern Standard Time. During daylight time you may want `0 11 * * *` for 7:00 AM local — edit `.github/workflows/daily-briefing.yml`.

## Customization (all in `config.py`)

### News topics and lengths

Edit `NEWS_TOPICS`: each entry has `query`, `length`, and `category` (feeds RSS/Google topic buckets).

### Stock watchlist

Edit `WATCHLIST_STOCKS` — list of ticker symbols as strings, e.g.:

```python
WATCHLIST_STOCKS = ["COF", "AXP", "AMZN", "BRK.B", "COST", "GOOGL", "NFLX", "SPOT", "XOM"]
```

Commit and push when you change this file so GitHub Actions picks up the new list.

### Sports teams

Edit `SPORTS_TEAMS`: `name`, `sport`, `espn_slug`, `espn_id`.

## Email-to-SMS

Email is sent to `<10-digit>@<carrier-gateway>` (e.g. `2125551234@tmomail.net`). That uses the same Gmail SMTP credentials as fallback email. Messages over ~1500 characters go to `USER_EMAIL` as full email instead.

## Local scheduler (alternative)

```bash
python main.py
```

Uses `SEND_TIME` from `.env` (EST). Or use cron:

```bash
0 12 * * * cd /path/to/project && /path/to/.venv/bin/python main.py --now
```
