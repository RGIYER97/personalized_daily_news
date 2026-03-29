import time
import requests
import feedparser
from google import genai
from datetime import datetime, timedelta
import pytz
import config


MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]


def _gemini_call(client, prompt: str) -> str | None:
    """Call Gemini with retry + backoff. Returns text or None on failure."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = resp.text
            if text and text.strip():
                return text.strip()
            print(f"  [LLM] Empty response on attempt {attempt + 1}")
        except Exception as e:
            print(f"  [LLM] Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")

        if attempt < MAX_RETRIES - 1:
            delay = RETRY_DELAYS[attempt]
            print(f"  [LLM] Retrying in {delay}s...")
            time.sleep(delay)

    return None


# ---------------------------------------------------------------------------
# Headline fetching
# ---------------------------------------------------------------------------

def _fetch_newsapi_headlines(topic_cfg: dict) -> list[str]:
    """Fetch headlines from NewsAPI for a given topic config."""
    if not config.NEWSAPI_KEY:
        return []

    yesterday = (datetime.now(pytz.timezone(config.TIMEZONE)) - timedelta(days=1)).strftime("%Y-%m-%d")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": topic_cfg["query"],
        "from": yesterday,
        "to": yesterday,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": 10,
        "apiKey": config.NEWSAPI_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        return [
            f"- {a['title']}. {a.get('description', '')}"
            for a in articles if a.get("title")
        ]
    except Exception as e:
        print(f"  [NewsAPI] Error fetching '{topic_cfg['query']}': {e}")
        return []


_RSS_FEEDS = {
    "business": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    ],
    "general": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    ],
    "technology": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://news.google.com/rss/search?q=technology&hl=en-US&gl=US&ceid=US:en",
    ],
}


def _fetch_rss_headlines(topic_cfg: dict) -> list[str]:
    """Fallback: pull headlines from RSS feeds via requests + feedparser."""
    category = topic_cfg.get("category", "general")
    feeds = _RSS_FEEDS.get(category, _RSS_FEEDS["general"])
    headlines = []
    yesterday = datetime.now(pytz.timezone(config.TIMEZONE)) - timedelta(days=1)

    for feed_url in feeds:
        try:
            resp = requests.get(feed_url, timeout=10)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.text)
            for entry in parsed.entries[:7]:
                pub = entry.get("published_parsed")
                if pub:
                    pub_date = datetime(*pub[:6], tzinfo=pytz.utc)
                    if pub_date.date() < (yesterday.date() - timedelta(days=1)):
                        continue
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                headlines.append(f"- {title}. {summary}")
        except Exception as e:
            print(f"  [RSS] Error fetching {feed_url}: {e}")
    return headlines[:15]


def _get_gemini_client():
    """Create and return a Gemini client, or None if no key."""
    if not config.GEMINI_API_KEY:
        return None
    return genai.Client(api_key=config.GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# News: single consolidated LLM call for ALL topics
# ---------------------------------------------------------------------------

def _build_raw_fallback(all_headlines: dict[str, list[str]]) -> str:
    """Format raw headlines as fallback when the LLM is unavailable."""
    sections = []
    for topic_name, headlines in all_headlines.items():
        if headlines:
            lines = "\n".join(headlines[:4])
            sections.append(f"📰 {topic_name}\n{lines}")
        else:
            sections.append(f"📰 {topic_name}\nNo recent headlines found.")
    return "\n\n".join(sections)


def fetch_news() -> str:
    """Fetch headlines for all topics, then synthesize in ONE Gemini call."""
    print("[News] Fetching headlines...")
    client = _get_gemini_client()

    all_headlines: dict[str, list[str]] = {}
    for topic_name, topic_cfg in config.NEWS_TOPICS.items():
        print(f"  Fetching: {topic_name}...")
        headlines = _fetch_newsapi_headlines(topic_cfg)
        if not headlines:
            print(f"  Falling back to RSS for {topic_name}...")
            headlines = _fetch_rss_headlines(topic_cfg)
        all_headlines[topic_name] = headlines

    if client is None:
        print("  [LLM] No GEMINI_API_KEY — returning raw headlines.")
        return _build_raw_fallback(all_headlines)

    # Build one combined prompt with all topics and their length constraints
    topic_blocks = []
    for topic_name, headlines in all_headlines.items():
        length = config.NEWS_TOPICS[topic_name]["length"]
        if headlines:
            text = "\n".join(headlines)
            topic_blocks.append(
                f"=== SECTION: {topic_name} ===\n"
                f"Length constraint: {length}\n"
                f"Raw headlines:\n{text}"
            )
        else:
            topic_blocks.append(
                f"=== SECTION: {topic_name} ===\n"
                f"Length constraint: {length}\n"
                f"Raw headlines: NONE FOUND"
            )

    combined = "\n\n".join(topic_blocks)
    topic_names = list(all_headlines.keys())

    prompt = (
        "You are a senior news editor writing a concise morning briefing.\n\n"
        "Below are raw headlines grouped by section. For EACH section, write a "
        "blunt, factual summary that obeys its length constraint.\n\n"
        f"{combined}\n\n"
        "STRICT RULES:\n"
        "1. Output one section per topic. Start each with the section name on its own line "
        f"(exactly: {', '.join(topic_names)}).\n"
        "2. Under each section name, write the summary as plain prose paragraphs.\n"
        "3. State WHAT happened and WHY it matters. Be specific: names, numbers, outcomes.\n"
        "4. NEVER repeat or quote article titles. Rewrite everything in your own words.\n"
        "5. NEVER include source names like 'BBC reports' or 'according to NYT'. Just state facts.\n"
        "6. Omit trivial, celebrity, or off-topic stories.\n"
        "7. No bullet points, no numbered lists, no markdown formatting.\n"
        "8. If no headlines were found for a section, write 'No notable developments reported.'\n"
        "9. Do NOT add any intro, closing, or meta-commentary.\n\n"
        "Begin."
    )

    print("  [LLM] Synthesizing all news sections (1 call)...")
    result = _gemini_call(client, prompt)

    if result:
        # Parse the LLM output into labeled sections
        sections = _parse_llm_sections(result, topic_names)
        return "\n\n".join(f"📰 {name}\n{body}" for name, body in sections.items())

    print("  [LLM] All retries failed — returning raw headlines.")
    return _build_raw_fallback(all_headlines)


def _parse_llm_sections(text: str, expected: list[str]) -> dict[str, str]:
    """Split LLM output into topic sections by looking for section headers."""
    sections: dict[str, str] = {}
    lines = text.split("\n")

    current_name = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip().rstrip(":")
        # Check if this line is a section header
        matched = None
        for name in expected:
            if stripped.lower() == name.lower() or stripped.lower().startswith(name.lower()):
                matched = name
                break

        if matched:
            if current_name:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = matched
            current_lines = []
        else:
            current_lines.append(line)

    if current_name:
        sections[current_name] = "\n".join(current_lines).strip()

    # Fill in any missing sections
    for name in expected:
        if name not in sections or not sections[name]:
            sections[name] = "No notable developments reported."

    return sections


# ---------------------------------------------------------------------------
# Stock watchlist: single consolidated LLM call
# ---------------------------------------------------------------------------

def _fetch_all_stock_headlines(symbols: list[str]) -> dict[str, list[str]]:
    """Fetch raw headlines for each ticker."""
    all_headlines: dict[str, list[str]] = {}
    yesterday = (datetime.now(pytz.timezone(config.TIMEZONE)) - timedelta(days=1)).strftime("%Y-%m-%d")

    for symbol in symbols:
        print(f"  Checking: {symbol}...")
        headlines = []

        if config.NEWSAPI_KEY:
            try:
                resp = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": f'"{symbol}" stock',
                        "from": yesterday,
                        "to": yesterday,
                        "sortBy": "relevancy",
                        "language": "en",
                        "pageSize": 5,
                        "apiKey": config.NEWSAPI_KEY,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                for a in resp.json().get("articles", []):
                    if a.get("title"):
                        headlines.append(f"- {a['title']}. {a.get('description', '')}")
            except Exception:
                pass

        if not headlines:
            try:
                rss_url = (
                    f"https://news.google.com/rss/search?"
                    f"q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"
                )
                resp = requests.get(rss_url, timeout=10)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries[:5]:
                    title = entry.get("title", "")
                    headlines.append(f"- {title}")
            except Exception:
                pass

        all_headlines[symbol] = headlines

    return all_headlines


def fetch_stock_news() -> str:
    """Fetch and summarize news for the configured stock watchlist."""
    if not config.WATCHLIST_STOCKS:
        return ""

    print("[Stocks] Checking watchlist...")
    client = _get_gemini_client()
    all_headlines = _fetch_all_stock_headlines(config.WATCHLIST_STOCKS)

    # Fallback if no LLM
    if client is None:
        lines = []
        for sym, hdls in all_headlines.items():
            if hdls:
                lines.append(f"{sym}: {hdls[0].lstrip('- ')}")
            else:
                lines.append(f"{sym}: No notable news.")
        return "📈 Stock Watchlist\n" + "\n".join(lines)

    # Build single prompt for all tickers
    block_parts = []
    for sym, hdls in all_headlines.items():
        if hdls:
            block_parts.append(f"[{sym}]\n" + "\n".join(hdls))
        else:
            block_parts.append(f"[{sym}]\nNo headlines found.")
    combined = "\n\n".join(block_parts)

    prompt = (
        "You are a financial news analyst writing a stock watchlist briefing.\n\n"
        f"Below are raw headlines for each ticker from the last 24 hours:\n\n"
        f"{combined}\n\n"
        "STRICT RULES:\n"
        "1. For each ticker, write ONE blunt sentence about any meaningful news "
        "(earnings, lawsuits, major deals, analyst upgrades/downgrades, regulatory action, "
        "significant price moves, executive changes).\n"
        "2. If a headline is just an opinion piece, portfolio advice, or generic market "
        "commentary with no real news, treat it as 'No notable news.'\n"
        "3. NEVER copy or quote article titles. Rewrite the fact in your own words.\n"
        "4. NEVER include source names like 'Seeking Alpha reports' or 'per CNBC'.\n"
        "5. Format: one line per ticker, starting with the ticker symbol and a colon.\n"
        "6. Do NOT add any header, intro, or closing.\n\n"
        "Begin."
    )

    print("  [LLM] Summarizing stock watchlist (1 call)...")
    result = _gemini_call(client, prompt)

    if result:
        return "📈 Stock Watchlist\n" + result

    # Fallback to raw first headline per ticker
    print("  [LLM] All retries failed — returning raw headlines.")
    lines = []
    for sym, hdls in all_headlines.items():
        if hdls:
            lines.append(f"{sym}: {hdls[0].lstrip('- ')}")
        else:
            lines.append(f"{sym}: No notable news.")
    return "📈 Stock Watchlist\n" + "\n".join(lines)
