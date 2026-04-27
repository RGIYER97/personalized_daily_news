import sys
import time
from datetime import datetime
import pytz
import schedule

import config
from news_fetcher import fetch_news, fetch_stock_news
from sports_fetcher import fetch_sports
from weather_fetcher import fetch_weather
from calendar_fetcher import fetch_calendar_events
from fun_fact_fetcher import fetch_fun_fact
from birthday_fetcher import fetch_birthdays
from notifier import deliver


def build_briefing() -> str:
    """Assemble the full daily briefing."""
    est = pytz.timezone(config.TIMEZONE)
    now = datetime.now(est)
    date_header = now.strftime("%A, %B %-d, %Y")

    header = f"☀️ Good Morning! Daily Briefing for {date_header}\n{'=' * 50}"

    weather_line = fetch_weather()
    calendar_section = fetch_calendar_events()
    birthday_section = fetch_birthdays()
    news_section = fetch_news()
    stock_section = fetch_stock_news()
    sports_section = fetch_sports()
    fun_fact_section = fetch_fun_fact()

    parts = [header]
    if weather_line:
        parts.append(weather_line)
    if calendar_section:
        parts.append("--- CALENDAR ---")
        parts.append(calendar_section)
    if birthday_section:
        parts.append(birthday_section)
    parts.append("--- NEWS ---")
    parts.append(news_section)
    if stock_section:
        parts.append("--- STOCKS ---")
        parts.append(stock_section)
    parts.append("--- SPORTS ---")
    parts.append(sports_section)
    if fun_fact_section:
        parts.append(fun_fact_section)
    parts.append("— End of Briefing —")

    briefing = "\n\n".join(parts)

    return briefing


def run_daily_job():
    """The job that runs every morning."""
    print(f"\n{'=' * 60}")
    print(f"[Main] Starting daily briefing at {datetime.now()}")
    print(f"{'=' * 60}\n")

    try:
        briefing = build_briefing()
        deliver(briefing)
        print("\n[Main] Daily briefing complete.\n")
    except Exception as e:
        print(f"\n[Main] FATAL ERROR during briefing: {e}\n")
        import traceback
        traceback.print_exc()


def main():
    if "--now" in sys.argv:
        print("[Main] Running immediately (--now flag detected)...")
        run_daily_job()
        return

    send_time = config.SEND_TIME
    print(f"[Main] Scheduler started. Briefing will be sent daily at {send_time} EST.")
    print(f"[Main] Press Ctrl+C to stop.\n")

    schedule.every().day.at(send_time).do(run_daily_job)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n[Main] Scheduler stopped by user.")


if __name__ == "__main__":
    main()
