import random
import time
import requests
from datetime import datetime
import pytz

import config
import llm_client

_BETWEEN_CALLS_DELAY = 25


def _fetch_wikipedia_on_this_day(month: int, day: int) -> dict:
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{month}/{day}"
    try:
        resp = requests.get(
            url, timeout=10, headers={"User-Agent": "DailyBriefing/1.0"}
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [FunFact] Wikipedia API error: {e}")
        return {}


def _build_source_text(data: dict) -> str:
    lines = []

    holidays = data.get("holidays", [])
    if holidays:
        lines.append("OBSERVANCES / NATIONAL DAYS:")
        for h in holidays[:12]:
            lines.append(f"- {h.get('text', '')}")
        lines.append("")

    # Prefer Wikipedia's own curated "selected" events; fall back to full event list.
    selected = data.get("selected") or data.get("events", [])
    if selected:
        lines.append("NOTABLE HISTORICAL EVENTS ON THIS DATE:")
        sample = random.sample(selected, min(20, len(selected)))
        sample.sort(key=lambda e: e.get("year") or 0)
        for e in sample:
            year = e.get("year", "")
            text = e.get("text", "")
            lines.append(f"- {year}: {text}")
        lines.append("")

    births = data.get("births", [])
    if births:
        lines.append("NOTABLE PEOPLE BORN ON THIS DATE:")
        for b in random.sample(births, min(10, len(births))):
            year = b.get("year", "")
            text = b.get("text", "")
            lines.append(f"- {year}: {text}")

    return "\n".join(lines)


def fetch_fun_fact() -> str:
    """Fetch Wikipedia On This Day data, then use the LLM to craft the best fun fact."""
    est = pytz.timezone(config.TIMEZONE)
    now = datetime.now(est)
    today_str = now.strftime("%A, %B %-d, %Y")

    print("[FunFact] Fetching Wikipedia On This Day data...")
    wiki_data = _fetch_wikipedia_on_this_day(now.month, now.day)
    source_text = _build_source_text(wiki_data) if wiki_data else ""

    if not llm_client.any_llm_configured():
        events = wiki_data.get("selected") or wiki_data.get("events", [])
        if events:
            e = random.choice(events)
            year = e.get("year", "?")
            text = e.get("text", "No fact available.")
            return f"💡 Fun Fact\nOn this date in {year}: {text}"
        return ""

    source_section = (
        f"Here are real facts and observances from Wikipedia for {today_str}:\n\n{source_text}\n\n"
        if source_text
        else f"Today is {today_str}. Draw on your own knowledge to find a great fact for this date.\n\n"
    )

    prompt = (
        f"You are writing the 'Fun Fact of the Day' for a morning briefing on {today_str}. "
        "The goal is one genuinely surprising fact that would spark a great conversation "
        "between a couple at home.\n\n"
        f"{source_section}"
        "Choose OR craft ONE fun fact from any of these categories:\n"
        "- A surprising or little-known historical event that happened on this date\n"
        "- A national / international observance or awareness day that is genuinely interesting\n"
        "- A fascinating science, nature, space, food, or technology fact\n"
        "- A surprising fact about a well-known person born on this date\n\n"
        "RULES:\n"
        "1. ABSOLUTELY NO politics, politicians, religion, or controversial social topics.\n"
        "2. Aim for the 'wow, I had no idea!' reaction — pick the most surprising option available.\n"
        "3. Keep it to 2–3 sentences. Be specific and concrete; include real names, dates, numbers.\n"
        "4. Start directly with the fact. No 'Fun Fact:' prefix, no 'Did you know', no intro phrase.\n"
        "5. Do NOT mention Wikipedia or any source by name.\n\n"
        "Output only the fun fact text, nothing else."
    )

    print(f"  [LLM] Waiting {_BETWEEN_CALLS_DELAY}s before fun fact call...")
    time.sleep(_BETWEEN_CALLS_DELAY)
    print("  [LLM] Generating fun fact...")
    result = llm_client.complete(prompt)

    if result:
        return f"💡 Fun Fact\n{result.strip()}"

    # LLM failed — fall back to a raw Wikipedia event
    events = wiki_data.get("selected") or wiki_data.get("events", [])
    if events:
        e = random.choice(events)
        year = e.get("year", "?")
        text = e.get("text", "No fact available.")
        return f"💡 Fun Fact\nOn this date in {year}: {text}"

    return ""
