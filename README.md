# Daily News & Sports Briefing

A Python-based daily news and sports aggregator that runs every morning via GitHub Actions, synthesizes headlines with an LLM, and delivers a briefing via SMS or email — all using free services.

## Features

- **News Synthesizer** — Pulls headlines from NewsAPI (with RSS fallback) across four categories: Economic & Financial, Geopolitics, General News, and Technology. Uses Google Gemini to synthesize them into concise summaries with configurable lengths.
- **Sports Desk** — Checks ESPN for yesterday's results and today's schedule for: Oakland Athletics, New York Mets, Las Vegas Raiders, Sacramento Kings, Los Angeles Lakers, Real Madrid, and Formula 1.
- **Free SMS Delivery** — Sends texts via Email-to-SMS carrier gateways (no Twilio or paid service needed). Falls back to full email if the message is too long.
- **GitHub Actions Automation** — Runs automatically at 7:00 AM EST every day via a cron workflow. No server or always-on laptop required.

## Project Structure

```
main.py                              — Orchestrator and scheduler
news_fetcher.py                      — News fetching (NewsAPI + RSS) and LLM synthesis
sports_fetcher.py                    — ESPN scores and schedules
notifier.py                         — SMS (Email-to-SMS gateway) and email delivery
config.py                           — Centralized configuration (reads from .env)
.env.example                        — Template showing all required variables
.github/workflows/daily-briefing.yml — GitHub Actions cron workflow
```

## Setup

### 1. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

| Variable | Source | Cost |
|---|---|---|
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) | Free (100 req/day) |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | Free tier available |
| `USER_PHONE` | Your 10-digit US phone number (e.g. `2125551234`) | — |
| `USER_CARRIER` | Your carrier (see table below) | — |
| `USER_EMAIL` | Your email (for fallback delivery) | — |
| `SMTP_EMAIL` | Gmail address for sending | Free |
| `SMTP_PASSWORD` | [Gmail App Password](https://myaccount.google.com/apppasswords) | Free |

### Supported Carriers

| Carrier | `USER_CARRIER` value |
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

### 3. Test Locally

```bash
python main.py --now
```

## GitHub Actions Setup (Recommended)

This is the best way to run the briefing daily without keeping your laptop on. GitHub Actions free tier gives you 2,000 minutes/month — this workflow uses ~1 minute per run.

### Step 1: Clone or push to GitHub

If you already have this repo (e.g. [RGIYER97/personalized_daily_news](https://github.com/RGIYER97/personalized_daily_news)), you only need to add secrets below.

Otherwise:

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Keep `.env` out of git — it is listed in `.gitignore`.

### Step 2: Add Secrets

Go to your repo on GitHub, then **Settings > Secrets and variables > Actions > New repository secret**.

Add each of these as a separate secret:

| Secret Name | Value |
|---|---|
| `NEWSAPI_KEY` | Your NewsAPI key |
| `GEMINI_API_KEY` | Your Gemini API key |
| `USER_PHONE` | Your 10-digit phone number (e.g. `2125551234`) |
| `USER_CARRIER` | Your carrier (e.g. `tmobile`) |
| `USER_EMAIL` | Your email address |
| `SMTP_EMAIL` | Your Gmail address |
| `SMTP_PASSWORD` | Your Gmail App Password |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |

### Step 3: Verify It Works

1. Go to the **Actions** tab in your GitHub repo
2. Click **Daily News Briefing** in the left sidebar
3. Click **Run workflow** > **Run workflow** (the green button)
4. Watch the run complete — you should receive an SMS within a minute

### Step 4: Done

The workflow is scheduled to run automatically at **7:00 AM EST every day**. You can check past runs anytime under the Actions tab.

**Adjusting the time:** Edit the cron expression in `.github/workflows/daily-briefing.yml`. GitHub Actions uses UTC:

```yaml
schedule:
  - cron: "0 12 * * *"   # 12:00 UTC = 7:00 AM EST
  # - cron: "0 11 * * *" # 11:00 UTC = 7:00 AM EDT (daylight saving)
```

## Customization

### News Topics & Summary Lengths

Edit the `NEWS_TOPICS` dictionary in `config.py`:

```python
NEWS_TOPICS = {
    "Economic & Financial": {
        "query": "economy OR finance OR stock market",
        "length": "1 paragraph (4-5 sentences)",
        "category": "business",
    },
    # Add or modify topics here...
}
```

### Sports Teams

Edit the `SPORTS_TEAMS` list in `config.py`. Each entry needs:
- `name` — Display name
- `sport` — One of: baseball, football, basketball, soccer, racing
- `espn_slug` — ESPN league identifier (mlb, nfl, nba, esp.1, f1)
- `espn_id` — ESPN team ID (use `None` for racing/F1)

## How the Email-to-SMS Gateway Works

Every US carrier has a free email gateway that converts emails into text messages. The system sends an email to `<your-10-digit-number>@<carrier-gateway>` (e.g. `2125551234@tmomail.net` for T-Mobile), and it arrives as a regular SMS on your phone. No sign-up, API keys, or payment required — it just uses your existing Gmail SMTP credentials.

If the briefing is too long for SMS (>1500 chars), it automatically falls back to sending a full email to your `USER_EMAIL` instead.

## Local Scheduler (Alternative)

If you prefer running this on your own machine or server instead of GitHub Actions:

```bash
# Runs the scheduler loop, sends briefing at SEND_TIME every day
python main.py

# Or use cron directly
# crontab -e
0 12 * * * cd /path/to/project && /path/to/.venv/bin/python main.py --now
```
