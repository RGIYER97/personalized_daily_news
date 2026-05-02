# Daily News & Sports Briefing

A Python-based daily morning briefing that runs via GitHub Actions, synthesizes news with an LLM, and delivers everything via email — all using free services.

Repository: [RGIYER97/personalized_daily_news](https://github.com/RGIYER97/personalized_daily_news)

## Features

- **Weather** — Today’s condition, high/low (°F), and any upcoming rain/snow/storm windows with start–end times (e.g. `Rain 2 PM–5 PM`). Uses [Open-Meteo](https://open-meteo.com) — no API key required. Defaults to Harrison, NJ; override with any lat/lon in `.env`.
- **Apple Calendar** — Today’s events from iCloud, sorted by time, shown as a daily agenda. Uses iCloud CalDAV with an app-specific password — works in GitHub Actions without a browser. Optional; skipped gracefully if credentials are not set.
- **News synthesizer** — Fetches headlines from NewsAPI (optional) plus many **public RSS feeds** (see below). **One LLM call** synthesizes all four topic sections into a **bulleted digest** of the most critical stories (one bullet per story, `• ` lines). Bullet count is **dynamic per day**: fewer bullets when news is quiet, more up to each section’s cap when the day is heavy — not pasted article titles. After the LLM responds, two post-processing passes run: a **cross-section deduplication** pass (Jaccard keyword similarity) removes any story that already appeared in an earlier section, and a **quality filter** drops bullets that lack named entities or are too short to be real news. Routine earnings for watchlist tickers are excluded from news sections since the stock section covers them.
- **LLM reliability (Gemini + Groq)** — Summaries use [Google Gemini](https://aistudio.google.com/apikey) first, trying current models in order: **Gemini 3 Flash → Gemini 2.5 Flash → Gemini 2.5 Flash-Lite → Gemini 3.1 Flash-Lite** (per [Google’s model list](https://ai.google.dev/gemini-api/docs/models)). **404** skips to the next ID; **429** waits 45s and retries. If all Gemini models fail, it falls back to **[Groq](https://console.groq.com)** (free tier, separate quota): Llama 3.3 / 3.1 / Mixtral. Set `LLM_GEMINI_FIRST=false` to use Groq first. There is a **~25s pause** between the news and stock LLM calls. CI jobs allow **45 minutes** for retries.
- **Stock watchlist** — Opens with a **market snapshot** (S&P 500, Nasdaq, Dow day performance) and an **earnings calendar** listing any watchlist tickers reporting in the next 3 days. Each ticker then shows price, day %, and YTD %; tickers that moved ≥ 3% on the day also show **52-week high/low context** (e.g. `near 52-wk low`). Price data is cross-checked against yfinance `fast_info` to catch stale or split-adjusted history values. Edit `WATCHLIST_STOCKS` in `config.py`.
- **Sports desk** — ESPN for yesterday’s results and today’s schedule: Oakland Athletics, New York Mets, Las Vegas Raiders, Sacramento Kings, Los Angeles Lakers, Real Madrid, Formula 1. **Playoff series records** are appended automatically when available (e.g. `Rockets lead series 3-2`).
- **GitHub Actions** — Scheduled daily run; no always-on laptop required.

## Briefing order

Each run outputs: **Header → Weather → Calendar → News → Stocks → Sports → footer.**

Weather always appears (no credentials needed). Calendar appears only when `APPLE_ID` and `APPLE_APP_PASSWORD` are set.

## News sources: do you need to log in?

**No extra credentials are required for RSS.** The app uses **public** feed URLs (headlines + short blurbs). That includes **WSJ**, **CNBC**, **NPR**, **BBC**, **NYT**, **Google News**, and sports data from **ESPN**.

| What | Credentials? |
|---|---|
| WSJ / CNBC / NPR / BBC / NYT / Google News RSS | **None** — these are standard public RSS endpoints. An individual WSJ.com account does **not** unlock the RSS feeds in code; you are not signing in per request. |
| NewsAPI | **Yes** — `NEWSAPI_KEY` in `.env` or GitHub Secrets (free tier available). |
| Google Gemini (summaries) | **Optional but recommended** — `GEMINI_API_KEY`. |
| Groq (summaries fallback) | **Optional** — `GROQ_API_KEY`. Use when Gemini always returns 429/404. At least one of Gemini or Groq should be set or output stays raw headlines. **Do not paste keys in chat** — use `.env` and GitHub Secrets only. |

Full article pages on publisher sites may still require a subscription in a browser; the briefing only uses what the RSS items expose.

### Feeds used by category (RSS fallback / enrichment)

Configured in `news_fetcher.py`:

- **Economic & Financial:** WSJ US Business, WSJ Markets, BBC Business, NYT Business, CNBC top stories, Guardian Business, FT, Politico Economy, Google News (business topic).
- **Geopolitics / General News:** WSJ World, BBC World, NYT World, CNBC world, NPR top stories, BBC main feed, Guardian World, Politico Politics, Google News US.
- **Technology:** WSJ tech, BBC tech, NYT tech, CNBC tech, Guardian tech, Ars Technica, MIT Technology Review.

Stock tickers also use NewsAPI when configured, otherwise Google News RSS search per symbol.

## Project structure

```
main.py                              — Orchestrator and scheduler
weather_fetcher.py                   — Open-Meteo forecast (no key required)
calendar_fetcher.py                  — Apple Calendar via iCloud CalDAV
llm_client.py                        — Gemini + Groq completion with retries
news_fetcher.py                      — News + stock headlines, LLM synthesis
sports_fetcher.py                    — ESPN scores and schedules
notifier.py                          — Gmail SMTP email delivery
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
| `NEWSAPI_KEY` | [NewsAPI](https://newsapi.org) | Free tier; extra headlines beyond RSS |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | Primary summarizer; try with [Groq](https://console.groq.com) if you hit 429s |
| `GROQ_API_KEY` | [Groq console](https://console.groq.com) | **Free** fallback when Gemini is rate-limited or returns 404 |
| `LLM_GEMINI_FIRST` | `true` or `false` | Set `false` to call **Groq before Gemini** |
| `USER_EMAIL` | Your inbox | Briefing recipient |
| `SMTP_EMAIL` | Gmail used to send | Often same as `USER_EMAIL` |
| `SMTP_PASSWORD` | [Gmail App Password](https://myaccount.google.com/apppasswords) | Not your normal Gmail login password |
| `SMTP_HOST` / `SMTP_PORT` | Usually `smtp.gmail.com` / `587` | |
| `APPLE_ID` | Your Apple ID email | Optional; enables Apple Calendar section |
| `APPLE_APP_PASSWORD` | App-specific password from [appleid.apple.com](https://appleid.apple.com) | Generate under Security → App-Specific Passwords |
| `WEATHER_LAT` / `WEATHER_LON` | Latitude / longitude | Optional; defaults to Harrison, NJ (`40.7459` / `-74.1543`) |
| `WEATHER_CITY_NAME` | Display name for weather line | Optional; defaults to `Harrison, NJ` |

### 3. Test locally

```bash
python main.py --now
```

## GitHub Actions + cron-job.org (recommended)

The briefing runs on GitHub Actions. An external cron service ([cron-job.org](https://cron-job.org)) triggers it daily via the GitHub API — this is more reliable than GitHub's built-in `schedule` trigger, which can silently skip or delay runs.

### Step 1: Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions** and add these repository secrets:

| Secret | Value |
|---|---|
| `NEWSAPI_KEY` | NewsAPI key |
| `GEMINI_API_KEY` | Gemini key (optional if Groq is set) |
| `GROQ_API_KEY` | Groq key (recommended when Gemini quota is tight) |
| `LLM_GEMINI_FIRST` | Optional: `false` to prefer Groq first |
| `USER_EMAIL` | Your email |
| `SMTP_EMAIL` | Gmail sender |
| `SMTP_PASSWORD` | Gmail App Password |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `APPLE_ID` | Your Apple ID email (optional) |
| `APPLE_APP_PASSWORD` | App-specific password from appleid.apple.com (optional) |

No WSJ, RSS, or weather-specific secrets are required. Weather works out of the box.

### Step 2: Create a GitHub Personal Access Token (PAT)

1. Go to [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta) (fine-grained tokens)
2. Click **Generate new token**
3. Name it something like `cron-briefing-trigger`
4. Set expiration (e.g. 1 year)
5. Under **Repository access**, select **Only select repositories** → choose `personalized_daily_news`
6. Under **Permissions → Repository permissions**, set **Actions** to **Read and write** (Metadata read-only is enabled by default)
7. Click **Generate token** and copy it — you'll need it in the next step

### Step 3: Set up cron-job.org

1. Sign up at [cron-job.org](https://cron-job.org) (free)
2. Click **Create cronjob**
3. Fill in:
   - **Title:** `Daily News Briefing`
   - **URL:**
     ```
     https://api.github.com/repos/RGIYER97/personalized_daily_news/actions/workflows/daily-briefing.yml/dispatches
     ```
   - **Schedule:** Every day at your desired time (e.g. **8:00 AM**), timezone **America/New_York**
   - **Request method:** `POST`
   - **Request headers** (click "Advanced" or "Headers"):
     ```
     Authorization: Bearer YOUR_GITHUB_PAT_HERE
     Accept: application/vnd.github+json
     ```
   - **Request body:**
     ```json
     {"ref":"main"}
     ```
4. Click **Create**

### Step 4: Verify

1. In cron-job.org, click **Test run** on your new job
2. Go to GitHub → **Actions** → confirm a new `Daily News Briefing` run appears
3. Check that the briefing email arrives

The cronjob will now fire daily at your configured time. You can also still trigger manually from the GitHub **Actions → Run workflow** button.

## Apple Calendar setup (optional)

To show today's events in the briefing:

1. Go to [appleid.apple.com](https://appleid.apple.com) → Sign In → **Security → App-Specific Passwords → Generate**
2. Label it something like `News Briefing` and copy the generated password (`xxxx-xxxx-xxxx-xxxx`)
3. Add to `.env`:
   ```
   APPLE_ID=you@icloud.com
   APPLE_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```
4. Add the same two values as GitHub Secrets (`APPLE_ID` and `APPLE_APP_PASSWORD`)

All iCloud calendars are fetched automatically. If the credentials are missing, the calendar section is silently skipped.

## Weather setup

No setup required — weather appears automatically using [Open-Meteo](https://open-meteo.com) (no API key). It defaults to **Harrison, NJ**. To change location, add to `.env`:

```
WEATHER_LAT=40.7128
WEATHER_LON=-74.0060
WEATHER_CITY_NAME=New York, NY
```

## Customization (all in `config.py`)

### News topics and bullet caps

Edit `NEWS_TOPICS`: each entry has `query`, `length`, and `category` (which RSS bucket is used when NewsAPI is empty).

The `length` field is passed to the LLM as a **maximum bullets** hint for that section (for example `up to 6 bullets`). The model uses fewer bullets on slow days and more (never above that cap) when there are many important stories. Adjust the wording or numbers in `length` to change how dense each section can get.

### Stock watchlist

Edit `WATCHLIST_STOCKS` — list of ticker symbols as strings, e.g.:

```python
WATCHLIST_STOCKS = ["COF", "AXP", "AMZN", "BRK.B", "COST", "GOOGL", "NFLX", "SPOT", "XOM"]
```

Commit and push when you change this file so GitHub Actions picks up the new list.

### Sports teams

Edit `SPORTS_TEAMS`: `name`, `sport`, `espn_slug`, `espn_id`.

## Email delivery

The briefing is sent to `USER_EMAIL` using Gmail SMTP. Set `SMTP_EMAIL` to your Gmail address and `SMTP_PASSWORD` to a [Gmail App Password](https://myaccount.google.com/apppasswords) (not your normal login password).

## Local scheduler (alternative)

```bash
python main.py
```

Uses `SEND_TIME` from `.env` (EST). Or use cron:

```bash
0 12 * * * cd /path/to/project && /path/to/.venv/bin/python main.py --now
```
