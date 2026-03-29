import requests
from datetime import datetime, timedelta
import pytz
import config


_ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"

_SPORT_MAP = {
    "baseball": "baseball",
    "football": "football",
    "basketball": "basketball",
    "soccer": "soccer",
    "racing": "racing",
}


def _get_espn_scoreboard(sport: str, league: str, date_str: str) -> dict:
    """Fetch ESPN scoreboard data for a sport/league on a given date (YYYYMMDD)."""
    espn_sport = _SPORT_MAP.get(sport, sport)
    url = _ESPN_SCOREBOARD_URL.format(sport=espn_sport, league=league)
    params = {"dates": date_str}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [ESPN] Error fetching {sport}/{league} for {date_str}: {e}")
        return {}


def _find_team_event(events: list, team_id: str | None, team_name: str, sport: str) -> dict | None:
    """Search events for one involving our tracked team."""
    for event in events:
        # F1: team_id is None, return the first event (there's usually one race per day)
        if sport == "racing" and team_id is None:
            return event

        for competition in event.get("competitions", []):
            for competitor in competition.get("competitors", []):
                cid = competitor.get("id", "")
                cname = competitor.get("team", {}).get("displayName", "")
                if str(cid) == str(team_id) or team_name.lower() in cname.lower():
                    return event
    return None


def _format_f1_result(event: dict) -> str | None:
    """Format an F1 race result showing the event name and top 3 finishers."""
    status = event.get("status", {}).get("type", {})
    if not status.get("completed", False):
        return None

    event_name = event.get("name", "Formula 1 Race")

    # Find the race competition (the last one with completed status, usually the main race)
    race_comp = None
    for comp in reversed(event.get("competitions", [])):
        comp_status = comp.get("status", {}).get("type", {})
        if comp_status.get("completed", False):
            race_comp = comp
            break

    if not race_comp:
        return f"{event_name} — Final (no detailed results available)"

    competitors = race_comp.get("competitors", [])
    top_3 = sorted(competitors, key=lambda c: c.get("order", 999))[:3]
    podium = []
    medals = ["1st", "2nd", "3rd"]
    for i, driver in enumerate(top_3):
        athlete = driver.get("athlete", {})
        name = athlete.get("displayName", f"Driver {i+1}")
        podium.append(f"{medals[i]}: {name}")

    return f"{event_name} — {', '.join(podium)}"


def _format_f1_schedule(event: dict) -> str | None:
    """Format a scheduled F1 event for today."""
    status = event.get("status", {}).get("type", {})
    if status.get("completed", False):
        return None

    event_name = event.get("name", "Formula 1")
    est = pytz.timezone(config.TIMEZONE)

    date_str = event.get("date", "")
    try:
        event_time = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(est)
        time_str = event_time.strftime("%-I:%M %p EST")
    except Exception:
        time_str = "TBD"

    broadcast = ""
    for comp in event.get("competitions", []):
        for b in comp.get("broadcasts", []):
            raw_names = b.get("names", [])
            for n in raw_names:
                if isinstance(n, str) and n:
                    broadcast = n
                    break
            if broadcast:
                break
        if broadcast:
            break

    line = f"Formula 1: {event_name} — {time_str}"
    if broadcast:
        line += f" (TV: {broadcast})"
    return line


def _format_yesterday_result(event: dict, team_id: str, team_name: str) -> str | None:
    """Format a completed game result for team sports."""
    status_type = event.get("status", {}).get("type", {}).get("name", "")
    completed = event.get("status", {}).get("type", {}).get("completed", False)
    if status_type not in ("STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_END_PERIOD") and not completed:
        return None

    competitions = event.get("competitions", [])
    if not competitions:
        return None

    comp = competitions[0]
    competitors = comp.get("competitors", [])
    if len(competitors) < 2:
        return None

    home = away = None
    for c in competitors:
        if c.get("homeAway") == "home":
            home = c
        else:
            away = c

    if not home or not away:
        home, away = competitors[0], competitors[1]

    home_name = home.get("team", {}).get("displayName", "")
    away_name = away.get("team", {}).get("displayName", "")
    home_score = home.get("score", "")
    away_score = away.get("score", "")

    if not home_name or not away_name or not home_score or not away_score:
        return None

    headline = ""
    for h in comp.get("headlines", []):
        headline = h.get("shortLinkText", "")
        break

    result = f"{away_name} {away_score} @ {home_name} {home_score}"
    if headline:
        result += f" — {headline}"

    return result


def _format_today_schedule(event: dict, team_id: str, team_name: str) -> str | None:
    """Format a scheduled game for today (team sports)."""
    status_name = event.get("status", {}).get("type", {}).get("name", "")
    if status_name in ("STATUS_FINAL", "STATUS_FULL_TIME"):
        return None

    competitions = event.get("competitions", [])
    if not competitions:
        return None
    comp = competitions[0]
    competitors = comp.get("competitors", [])

    if len(competitors) < 2:
        return None

    est = pytz.timezone(config.TIMEZONE)
    date_str = event.get("date", "")
    try:
        game_time = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(est)
        time_str = game_time.strftime("%-I:%M %p EST")
    except Exception:
        time_str = "TBD"

    broadcast = ""
    for b in comp.get("broadcasts", []):
        raw_names = b.get("names", [])
        for n in raw_names:
            if isinstance(n, str) and n:
                broadcast = n
                break
            elif isinstance(n, dict):
                broadcast = n.get("shortName", n.get("name", ""))
                if broadcast:
                    break
        if broadcast:
            break
    if not broadcast:
        for geo in comp.get("geoBroadcasts", []):
            media = geo.get("media", {})
            short = media.get("shortName", "")
            if short:
                broadcast = short
                break

    home = away = None
    for c in competitors:
        if c.get("homeAway") == "home":
            home = c
        else:
            away = c
    if not home or not away:
        home, away = competitors[0], competitors[1]

    home_name = home.get("team", {}).get("displayName", "Home")
    away_name = away.get("team", {}).get("displayName", "Away")

    our_team_is_home = str(home.get("id")) == str(team_id)
    if our_team_is_home:
        matchup = f"vs {away_name}"
    else:
        matchup = f"@ {home_name}"

    line = f"{team_name} {matchup} — {time_str}"
    if broadcast:
        line += f" (TV: {broadcast})"

    return line


def fetch_sports() -> str:
    """Main entry point: fetch yesterday's results and today's schedule."""
    print("[Sports] Fetching scores and schedules...")
    est = pytz.timezone(config.TIMEZONE)
    now = datetime.now(est)
    yesterday = now - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y%m%d")
    today_str = now.strftime("%Y%m%d")

    results = []
    schedule = []

    for team in config.SPORTS_TEAMS:
        sport = team["sport"]
        league = team["espn_slug"]
        team_id = team["espn_id"]
        team_name = team["name"]

        print(f"  Checking: {team_name}...")

        # Yesterday's results
        data = _get_espn_scoreboard(sport, league, yesterday_str)
        events = data.get("events", [])
        event = _find_team_event(events, team_id, team_name, sport)
        if event:
            if sport == "racing":
                result = _format_f1_result(event)
            else:
                result = _format_yesterday_result(event, team_id, team_name)
            if result:
                results.append(f"  • {result}")

        # Today's schedule
        if today_str != yesterday_str:
            data_today = _get_espn_scoreboard(sport, league, today_str)
        else:
            data_today = data
        events_today = data_today.get("events", [])
        event_today = _find_team_event(events_today, team_id, team_name, sport)
        if event_today:
            if sport == "racing":
                sched = _format_f1_schedule(event_today)
            else:
                sched = _format_today_schedule(event_today, team_id, team_name)
            if sched:
                schedule.append(f"  • {sched}")

    sections = []
    sections.append("🏟️ Yesterday's Results")
    if results:
        sections.append("\n".join(results))
    else:
        sections.append("  No games found for tracked teams yesterday.")

    sections.append("")
    sections.append("📅 Today's Schedule")
    if schedule:
        sections.append("\n".join(schedule))
    else:
        sections.append("  No tracked teams are playing today.")

    return "\n".join(sections)
