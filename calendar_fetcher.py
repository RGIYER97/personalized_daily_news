import caldav
from datetime import datetime, date, timedelta
import pytz
import config


def fetch_calendar_events() -> str:
    print("[Calendar] Fetching today's events from Apple Calendar...")

    if not config.APPLE_ID or not config.APPLE_APP_PASSWORD:
        print("[Calendar] No Apple credentials configured. Skipping.")
        return ""

    tz = pytz.timezone(config.TIMEZONE)
    today = datetime.now(tz).date()
    start = tz.localize(datetime.combine(today, datetime.min.time()))
    end = start + timedelta(days=1)

    try:
        client = caldav.DAVClient(
            url="https://caldav.icloud.com/",
            username=config.APPLE_ID,
            password=config.APPLE_APP_PASSWORD,
        )
        principal = client.principal()
        calendars = principal.calendars()

        events = []
        for cal in calendars:
            try:
                for event in cal.date_search(start=start, end=end, expand=True):
                    for component in event.icalendar_instance.walk("VEVENT"):
                        summary = str(component.get("SUMMARY", "Untitled"))
                        dtstart = component.get("DTSTART").dt

                        if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
                            sort_key = tz.localize(datetime.combine(dtstart, datetime.min.time()))
                            time_str = "All day"
                        else:
                            if dtstart.tzinfo is None:
                                dtstart = tz.localize(dtstart)
                            else:
                                dtstart = dtstart.astimezone(tz)
                            sort_key = dtstart
                            time_str = dtstart.strftime("%-I:%M %p")

                        events.append((sort_key, time_str, summary))
            except Exception as e:
                print(f"  [Calendar] Error reading a calendar: {e}")
                continue

        events.sort(key=lambda x: x[0])

        if not events:
            return "  No events scheduled today."

        return "\n".join(f"  • {time_str}: {summary}" for _, time_str, summary in events)

    except Exception as e:
        print(f"[Calendar] Error connecting to iCloud: {e}")
        return ""
