import requests
from datetime import datetime, timedelta
import pytz
import config

_WMO_DESCRIPTION = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Heavy freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Violent showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ heavy hail",
}

_ADVERSE_CODES = set(range(51, 100))


def _adverse_kind(max_code: int) -> str:
    if max_code >= 95:
        return "Storms"
    if max_code >= 71:
        return "Snow"
    return "Rain"


def _find_adverse_windows(
    hours: list[datetime], codes: list[int], now: datetime
) -> list[tuple[str, str, str]]:
    """Return list of (kind, start_str, end_str) for contiguous adverse periods from now onward."""
    windows = []
    start = None
    last_adverse = None

    for dt, code in zip(hours, codes):
        if dt < now:
            continue
        if code in _ADVERSE_CODES:
            if start is None:
                start = dt
            last_adverse = dt
        else:
            if start is not None:
                codes_in = [c for t, c in zip(hours, codes) if start <= t <= last_adverse]
                kind = _adverse_kind(max(codes_in))
                windows.append((kind, start.strftime("%-I %p"), last_adverse.strftime("%-I %p")))
                start = None
                last_adverse = None

    if start is not None:
        codes_in = [c for t, c in zip(hours, codes) if start <= t <= last_adverse]
        kind = _adverse_kind(max(codes_in))
        windows.append((kind, start.strftime("%-I %p"), last_adverse.strftime("%-I %p")))

    return windows


def fetch_weather() -> str:
    print("[Weather] Fetching forecast...")
    lat = config.WEATHER_LAT
    lon = config.WEATHER_LON
    city = config.WEATHER_CITY_NAME

    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": ["temperature_2m_max", "temperature_2m_min", "weathercode"],
                "hourly": ["weathercode"],
                "temperature_unit": "fahrenheit",
                "timezone": config.TIMEZONE,
                "forecast_days": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        daily = data["daily"]
        high = round(daily["temperature_2m_max"][0])
        low = round(daily["temperature_2m_min"][0])
        condition = _WMO_DESCRIPTION.get(daily["weathercode"][0], "Unknown")

        tz = pytz.timezone(config.TIMEZONE)
        now = datetime.now(tz)
        hourly = data["hourly"]
        hour_times = [tz.localize(datetime.fromisoformat(t)) for t in hourly["time"]]
        hour_codes = hourly["weathercode"]

        windows = _find_adverse_windows(hour_times, hour_codes, now)

        line = f"📍 {city}: {condition} | H: {high}°F / L: {low}°F"
        if windows:
            adverse_parts = [f"{kind} {s}–{e}" for kind, s, e in windows]
            line += " | " + ", ".join(adverse_parts)

        print(f"[Weather] {line}")
        return line

    except Exception as e:
        print(f"[Weather] Error fetching forecast: {e}")
        return ""
