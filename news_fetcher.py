import requests
import feedparser
from google import genai
from datetime import datetime, timedelta
import pytz
import config


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
        "pageSize": 15,
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
        "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTXpJU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
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


def _synthesize_with_llm(client, topic_name: str, length: str, raw_headlines: list[str]) -> str:
    """Use Gemini to synthesize headlines into a blunt, substantive briefing.

    Runs a two-pass process:
    1. Generate a summary from raw headlines.
    2. Validate the summary — if it reads like a list of titles or ads,
       the model rewrites it into a direct, factual summary.
    """
    if not raw_headlines:
        return f"No recent headlines found for {topic_name}."

    if client is None:
        return "\n".join(raw_headlines[:5])

    headlines_text = "\n".join(raw_headlines)

    # --- Pass 1: Synthesize ---
    synth_prompt = (
        f"You are a senior news editor writing a morning briefing for a busy reader. "
        f"Below are raw headlines and descriptions about '{topic_name}' from the last 24 hours.\n\n"
        f"Raw material:\n{headlines_text}\n\n"
        f"INSTRUCTIONS:\n"
        f"- Write a blunt, factual summary of the most important developments.\n"
        f"- State WHAT happened and WHY it matters. Do not just list article titles.\n"
        f"- Use plain, direct language. No filler, no hype, no clickbait phrasing.\n"
        f"- Combine related stories into single statements.\n"
        f"- Omit trivial, celebrity, or unrelated stories that don't fit '{topic_name}'.\n"
        f"- Do NOT use bullet points, numbered lists, or headings.\n"
        f"- Length: {length}.\n"
        f"- Do NOT start with 'Here is' or 'Here's' or any meta-commentary."
    )

    try:
        resp1 = client.models.generate_content(model="gemini-2.0-flash", contents=synth_prompt)
        draft = resp1.text.strip()
    except Exception as e:
        print(f"  [LLM] Error in synthesis pass for '{topic_name}': {e}")
        return "\n".join(raw_headlines[:3])

    # --- Pass 2: Quality check and rewrite if needed ---
    validate_prompt = (
        f"You are a quality editor. Review the following news summary and determine if it "
        f"is a genuine, informative summary or if it reads like a list of article titles, "
        f"advertisements, or clickbait.\n\n"
        f"Summary to review:\n\"{draft}\"\n\n"
        f"RULES:\n"
        f"- If the summary is substantive and informative, return it EXACTLY as-is.\n"
        f"- If the summary contains article titles, clickbait phrasing, ad-like language, "
        f"or lacks substance, rewrite it into a direct, factual summary.\n"
        f"- The rewrite must state concrete facts: names, numbers, outcomes.\n"
        f"- Length: {length}.\n"
        f"- Output ONLY the final summary text. No commentary, no labels, no quotes around it."
    )

    try:
        resp2 = client.models.generate_content(model="gemini-2.0-flash", contents=validate_prompt)
        return resp2.text.strip()
    except Exception as e:
        print(f"  [LLM] Error in validation pass for '{topic_name}': {e}")
        return draft


# ---------------------------------------------------------------------------
# Stock watchlist
# ---------------------------------------------------------------------------

def _fetch_stock_news(client, symbols: list[str]) -> str:
    """Fetch and summarize meaningful news for watched stocks."""
    if not symbols:
        return ""

    print("[Stocks] Checking watchlist...")

    # Gather headlines for all symbols from RSS / NewsAPI
    all_stock_headlines: dict[str, list[str]] = {}

    for symbol in symbols:
        print(f"  Checking: {symbol}...")
        headlines = []

        # Try NewsAPI first
        if config.NEWSAPI_KEY:
            yesterday = (datetime.now(pytz.timezone(config.TIMEZONE)) - timedelta(days=1)).strftime("%Y-%m-%d")
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

        # RSS fallback: Google News search for the ticker
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

        all_stock_headlines[symbol] = headlines

    # If no LLM, just return raw headlines
    if client is None:
        lines = []
        for sym, hdls in all_stock_headlines.items():
            if hdls:
                lines.append(f"{sym}: {hdls[0].lstrip('- ')}")
            else:
                lines.append(f"{sym}: No notable news.")
        return "\n".join(lines)

    # Build a single LLM call with all stock headlines
    block_parts = []
    for sym, hdls in all_stock_headlines.items():
        if hdls:
            block_parts.append(f"[{sym}]\n" + "\n".join(hdls))
        else:
            block_parts.append(f"[{sym}]\nNo headlines found.")
    combined = "\n\n".join(block_parts)

    prompt = (
        f"You are a financial news analyst writing a stock watchlist briefing.\n\n"
        f"Below are raw headlines for each ticker from the last 24 hours:\n\n"
        f"{combined}\n\n"
        f"INSTRUCTIONS:\n"
        f"- For each ticker, write ONE blunt sentence about any meaningful news "
        f"(earnings, lawsuits, major deals, analyst upgrades/downgrades, regulatory action, "
        f"significant price moves, executive changes).\n"
        f"- If there is no meaningful news for a ticker, write: \"No notable news.\"\n"
        f"- Do NOT repeat article titles. State the fact directly.\n"
        f"- Format: one line per ticker, starting with the ticker symbol.\n"
        f"- Example: \"AMZN: Amazon announced a $10B buyback after Q4 earnings beat estimates.\"\n"
        f"- Example: \"XOM: No notable news.\"\n"
        f"- Do NOT add any header, intro, or closing commentary."
    )

    try:
        resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"  [LLM] Error summarizing stock news: {e}")
        lines = []
        for sym, hdls in all_stock_headlines.items():
            if hdls:
                lines.append(f"{sym}: {hdls[0].lstrip('- ')}")
            else:
                lines.append(f"{sym}: No notable news.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_news() -> str:
    """Main entry point: fetch + synthesize all configured news topics."""
    print("[News] Fetching and synthesizing news...")
    client = _get_gemini_client()
    sections = []

    for topic_name, topic_cfg in config.NEWS_TOPICS.items():
        print(f"  Fetching: {topic_name}...")
        headlines = _fetch_newsapi_headlines(topic_cfg)
        if not headlines:
            print(f"  Falling back to RSS for {topic_name}...")
            headlines = _fetch_rss_headlines(topic_cfg)

        summary = _synthesize_with_llm(client, topic_name, topic_cfg["length"], headlines)
        sections.append(f"📰 {topic_name}\n{summary}")

    return "\n\n".join(sections)


def fetch_stock_news() -> str:
    """Fetch and summarize news for the configured stock watchlist."""
    if not config.WATCHLIST_STOCKS:
        return ""
    client = _get_gemini_client()
    summary = _fetch_stock_news(client, config.WATCHLIST_STOCKS)
    return f"📈 Stock Watchlist\n{summary}"
