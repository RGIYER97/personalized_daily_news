from datetime import datetime, date, timedelta
import pytz
import config

_LOOKAHEAD_DAYS = 7


def fetch_birthdays() -> str:
    """Return upcoming birthdays within the next 7 days (including today)."""
    if not config.BIRTHDAYS:
        return ""

    est = pytz.timezone(config.TIMEZONE)
    today = datetime.now(est).date()

    entries = []
    for person in config.BIRTHDAYS:
        name = person["name"]
        month = person["month"]
        day = person["day"]
        birth_year = person.get("year")

        # Find the next occurrence of this birthday on or after today.
        try:
            bday_this_year = date(today.year, month, day)
        except ValueError:
            continue  # skip invalid dates (e.g. Feb 29 in a non-leap year)

        if bday_this_year >= today:
            next_bday = bday_this_year
        else:
            try:
                next_bday = date(today.year + 1, month, day)
            except ValueError:
                continue

        days_away = (next_bday - today).days
        if days_away > _LOOKAHEAD_DAYS:
            continue

        age_str = ""
        if birth_year:
            age = next_bday.year - birth_year
            age_str = f", turns {age}"

        if days_away == 0:
            label = f"TODAY 🎉 — {name}{age_str}"
        elif days_away == 1:
            label = f"Tomorrow — {name}{age_str}"
        else:
            label = f"In {days_away} days ({next_bday.strftime('%b %-d')}) — {name}{age_str}"

        entries.append((days_away, label))

    if not entries:
        return ""

    entries.sort(key=lambda x: x[0])
    lines = "\n".join(f"• {label}" for _, label in entries)
    return f"🎂 Upcoming Birthdays\n{lines}"
