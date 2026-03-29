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
    ],
    "general": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.bbci.co.uk/news/rss.xml",
    ],
    "technology": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
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
    return headlines[:12]


def _synthesize_with_llm(topic_name: str, length: str, raw_headlines: list[str]) -> str:
    """Use Google Gemini to synthesize headlines into a briefing."""
    if not raw_headlines:
        return f"No recent headlines found for {topic_name}."

    if not config.GEMINI_API_KEY:
        return "\n".join(raw_headlines[:5])

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    headlines_text = "\n".join(raw_headlines)
    prompt = (
        f"You are a concise news briefing writer. Below are raw headlines and snippets "
        f"about '{topic_name}' from the last day.\n\n"
        f"Headlines:\n{headlines_text}\n\n"
        f"Synthesize these into a clear, informative summary. "
        f"Length constraint: {length}. "
        f"Write in a neutral, professional tone. Do not use bullet points. "
        f"Focus on the most impactful stories. Do not add a heading or title."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"  [LLM] Error synthesizing '{topic_name}': {e}")
        return "\n".join(raw_headlines[:3])


def fetch_news() -> str:
    """Main entry point: fetch + synthesize all configured news topics."""
    print("[News] Fetching and synthesizing news...")
    sections = []

    for topic_name, topic_cfg in config.NEWS_TOPICS.items():
        print(f"  Fetching: {topic_name}...")
        headlines = _fetch_newsapi_headlines(topic_cfg)
        if not headlines:
            print(f"  Falling back to RSS for {topic_name}...")
            headlines = _fetch_rss_headlines(topic_cfg)

        summary = _synthesize_with_llm(topic_name, topic_cfg["length"], headlines)
        sections.append(f"📰 {topic_name}\n{summary}")

    return "\n\n".join(sections)
