# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A Python-based daily news briefing system that fetches headlines from RSS feeds and optionally NewsAPI, synthesizes them via an LLM (Google Gemini or Groq), appends a stock watchlist and sports scores, then delivers the result via email-to-SMS gateway or fallback email. It runs on a schedule via GitHub Actions triggered by cron-job.org.

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

**Data flow:** `main.py` → `build_briefing()` → fetch news → fetch stocks → fetch sports → deliver

| File | Role |
|------|------|
| `main.py` | Orchestrator: `build_briefing()` ties everything together; `main()` starts scheduler or runs immediately |
| `config.py` | Central config loaded from `.env`; defines `NEWS_TOPICS`, `WATCHLIST_STOCKS`, `SPORTS_TEAMS` — user customizations go here |
| `news_fetcher.py` | Fetches RSS/NewsAPI headlines; makes **two consolidated LLM calls** (one for all 4 news topics, one for stocks) |
| `llm_client.py` | Dual-model client: Gemini primary with Groq fallback; handles 429 (45s wait + retry) and 404 (skip to next model) |
| `sports_fetcher.py` | ESPN public scoreboard API; no LLM, formats yesterday's scores and today's schedule |
| `notifier.py` | Delivers via email-to-SMS gateway (≤1500 chars) or email fallback |

## LLM Fallback Chain

When `LLM_GEMINI_FIRST=true` (default):
1. Gemini 3 Flash → 2.5 Flash → 2.5 Flash-Lite → 3.1 Flash-Lite
2. Groq: Llama 3.3 → 3.1 → Mixtral

Each model gets 3 attempts (12s delay between attempts for Gemini, 15s for Groq). If everything fails, raw unsynthesized headlines are returned. The 25s delay between the news and stock LLM calls is intentional rate-limit mitigation — do not remove it.

## Key Configuration

User-facing customization lives in `config.py`:
- `NEWS_TOPICS` — 4 sections with search query, `max_bullets` cap, and category
- `WATCHLIST_STOCKS` — list of ticker symbols
- `SPORTS_TEAMS` — list of dicts with `name`, `sport`, `espn_slug`, `espn_id`

Required `.env` variables (see `.env.example`): `GEMINI_API_KEY`, `GROQ_API_KEY` (at least one), `SMTP_EMAIL`, `SMTP_PASSWORD` (Gmail App Password), `USER_EMAIL`, `USER_PHONE`, `USER_CARRIER`. `NEWSAPI_KEY` is optional — the system falls back to RSS.

## GitHub Actions Deployment

The workflow at `.github/workflows/daily-briefing.yml` is triggered via an external HTTP POST from cron-job.org (not a GitHub schedule). It requires a fine-grained PAT with Actions read+write permissions, stored as a repo secret. All `.env` variables must also be added as GitHub Secrets. The CI timeout is 45 minutes to accommodate LLM retry delays.
