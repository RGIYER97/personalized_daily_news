# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A Python-based daily morning briefing system. It fetches weather, Apple Calendar events, news headlines (RSS + optional NewsAPI), stock watchlist news, and sports scores — synthesizes the news and stocks via an LLM (Google Gemini or Groq) — then delivers everything via email-to-SMS gateway or fallback email. Runs on a schedule via GitHub Actions triggered by cron-job.org.

## Running the Project

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in keys and phone/email config
python main.py --now   # run immediately (skip scheduler)
python main.py         # start local daily scheduler (uses SEND_TIME from .env)
```

There are no automated tests. The `--now` flag is the primary way to manually verify changes.

## Architecture

**Data flow:** `main.py` → `build_briefing()` → fetch weather → fetch calendar → fetch news → fetch stocks → fetch sports → deliver

| File | Role |
|------|------|
| `main.py` | Orchestrator: `build_briefing()` ties everything together; `main()` starts scheduler or runs immediately |
| `config.py` | Central config loaded from `.env`; defines `NEWS_TOPICS`, `WATCHLIST_STOCKS`, `SPORTS_TEAMS`, weather location, Apple credentials — user customizations go here |
| `weather_fetcher.py` | Open-Meteo API (no key); returns today's condition, high/low, and upcoming adverse-weather windows (rain/snow/storms) with start–end times |
| `calendar_fetcher.py` | iCloud CalDAV via `caldav`; fetches all Apple Calendar events for today sorted by time |
| `news_fetcher.py` | Fetches RSS/NewsAPI headlines; makes **two consolidated LLM calls** (one for all 4 news topics, one for stocks). Post-processes LLM output through `_deduplicate_sections` (Jaccard keyword similarity, removes cross-section repeats) and `_filter_low_quality_bullets` (drops bullets without named entities or under 12 words). Stock section prepends market indices (S&P 500, Nasdaq, Dow) and upcoming earnings for watchlist tickers. Price data is cross-checked against `fast_info` to catch stale/adjusted history; 52-week high/low context is appended for moves ≥ 3%. |
| `llm_client.py` | Dual-model client: Gemini primary with Groq fallback; handles 429 (45s wait + retry) and 404 (skip to next model) |
| `sports_fetcher.py` | ESPN public scoreboard API; no LLM, formats yesterday's scores and today's schedule. Appends playoff series record to both result and schedule lines when the ESPN `series` field is present. |
| `notifier.py` | Delivers via email-to-SMS gateway (≤1500 chars) or email fallback |

## LLM Fallback Chain

When `LLM_GEMINI_FIRST=true` (default):
1. Gemini 3 Flash → 2.5 Flash → 2.5 Flash-Lite → 3.1 Flash-Lite
2. Groq: Llama 3.3 → 3.1 → Mixtral

Each model gets 3 attempts (12s delay between attempts for Gemini, 15s for Groq). If everything fails, raw unsynthesized headlines are returned. The 25s delay between the news and stock LLM calls is intentional rate-limit mitigation — do not remove it.

## Post-processing pipeline (news sections)

After the LLM returns the news digest, three passes run in order:

1. `_parse_llm_sections` — splits raw LLM text into per-topic dicts
2. `_deduplicate_sections` — removes any bullet whose Jaccard keyword similarity to an earlier-section bullet is ≥ 0.3; first occurrence wins
3. `_filter_low_quality_bullets` — drops bullets with fewer than 12 words or no pattern matching two consecutive capitalized words (named-entity proxy)

The LLM prompt also instructs the model to exclude routine earnings/financials for any ticker already in `WATCHLIST_STOCKS` (covered in the stock section) and to skip stories for watchlist tickers unless they represent landmark regulatory or criminal events.

## Key Configuration

User-facing customization lives in `config.py`:
- `NEWS_TOPICS` — 4 sections with search query, `max_bullets` cap, and category
- `WATCHLIST_STOCKS` — list of ticker symbols
- `SPORTS_TEAMS` — list of dicts with `name`, `sport`, `espn_slug`, `espn_id`
- `WEATHER_LAT` / `WEATHER_LON` / `WEATHER_CITY_NAME` — defaults to Harrison, NJ; override via `.env`

Required `.env` variables (see `.env.example`): `GEMINI_API_KEY`, `GROQ_API_KEY` (at least one), `SMTP_EMAIL`, `SMTP_PASSWORD` (Gmail App Password), `USER_EMAIL`, `USER_PHONE`, `USER_CARRIER`. `NEWSAPI_KEY` is optional — the system falls back to RSS.

Optional `.env` variables: `APPLE_ID` + `APPLE_APP_PASSWORD` (app-specific password from appleid.apple.com) to enable Apple Calendar events in the briefing. Weather requires no credentials.

## GitHub Actions Deployment

The workflow at `.github/workflows/daily-briefing.yml` is triggered via an external HTTP POST from cron-job.org (not a GitHub schedule). It requires a fine-grained PAT with Actions read+write permissions, stored as a repo secret. All `.env` variables must also be added as GitHub Secrets. The CI timeout is 45 minutes to accommodate LLM retry delays.
