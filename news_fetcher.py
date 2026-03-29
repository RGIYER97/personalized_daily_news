import time
import requests
import feedparser
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import config
import llm_client


# Longer gap between the two LLM calls (news vs stocks) to reduce rate-limit bursts.
_BETWEEN_CALLS_DELAY = 25


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
        "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "https://www.theguardian.com/business/rss",
        "https://www.ft.com/world?format=rss",
        "https://rss.politico.com/economy.xml",
        "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    ],
    "general": [
        "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
        "https://feeds.npr.org/1001/rss.xml",
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://www.theguardian.com/world/rss",
        "https://rss.politico.com/politics-news.xml",
        "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    ],
    "technology": [
        "https://feeds.a.dj.com/rss/RSSWSJD.xml",
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        "https://www.theguardian.com/technology/rss",
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://news.google.com/rss/search?q=technology+AI&hl=en-US&gl=US&ceid=US:en",
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
            resp = requests.get(
                feed_url, timeout=10,
                headers={"User-Agent": "Mozilla/5.0 DailyBriefing/1.0"},
            )
            resp.raise_for_status()
            parsed = feedparser.parse(resp.text)
            for entry in parsed.entries[:10]:
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
    return headlines[:35]


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
    """Fetch headlines for all topics, then synthesize in ONE LLM call."""
    print("[News] Fetching headlines...")
    all_headlines: dict[str, list[str]] = {}
    for topic_name, topic_cfg in config.NEWS_TOPICS.items():
        print(f"  Fetching: {topic_name}...")
        headlines = _fetch_newsapi_headlines(topic_cfg)
        if not headlines:
            print(f"  Falling back to RSS for {topic_name}...")
            headlines = _fetch_rss_headlines(topic_cfg)
        all_headlines[topic_name] = headlines

    if not llm_client.any_llm_configured():
        print("  [LLM] No GEMINI_API_KEY or GROQ_API_KEY — returning raw headlines.")
        return _build_raw_fallback(all_headlines)

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
        "You are a senior editor at a major U.S. newspaper writing a morning intelligence briefing "
        "for a well-informed reader who wants substance, not filler.\n\n"
        "Below are raw headlines grouped by section. For EACH section, synthesize a "
        "factual summary that obeys its length constraint.\n\n"
        f"{combined}\n\n"
        "STRICT RULES:\n"
        "1. Output one section per topic. Start each with the section name on its own line "
        f"(exactly: {', '.join(topic_names)}).\n"
        "2. Under each section name, write the summary as plain prose paragraphs — "
        "no bullets, no numbered lists, no markdown.\n"
        "3. Always use real, specific names. Write 'Donald Trump', 'Jerome Powell', "
        "'Elon Musk', 'Benjamin Netanyahu' — never 'the president', 'the Fed chair', "
        "'a prominent CEO', or 'a foreign leader'.\n"
        "4. Always include specific figures where available: dollar amounts, percentages, "
        "vote counts, casualty counts, poll numbers.\n"
        "5. Cover only events of genuine U.S. national or worldwide significance. "
        "Skip local crime, celebrity gossip, sports, lifestyle, and opinion pieces.\n"
        "6. State WHAT happened, WHO was involved, and WHY it matters globally or for Americans.\n"
        "7. NEVER copy or quote article titles verbatim. Synthesize in your own words.\n"
        "8. NEVER attribute to a source ('BBC reports', 'per WSJ'). State facts directly.\n"
        "9. If a section has no headlines that are genuinely notable at a U.S. or global level, "
        "write exactly: 'No major developments reported for this period.'\n"
        "10. Do NOT add any intro sentence, closing sentence, or meta-commentary.\n\n"
        "Begin."
    )

    print("  [LLM] Synthesizing all news sections (1 call)...")
    result = llm_client.complete(prompt)

    if result:
        sections = _parse_llm_sections(result, topic_names)
        return "\n\n".join(f"📰 {name}\n{body}" for name, body in sections.items())

    print("  [LLM] All models exhausted — returning raw headlines.")
    return _build_raw_fallback(all_headlines)


def _parse_llm_sections(text: str, expected: list[str]) -> dict[str, str]:
    """Split LLM output into topic sections by looking for section headers."""
    sections: dict[str, str] = {}
    lines = text.split("\n")

    current_name = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip().rstrip(":")
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

    for name in expected:
        if name not in sections or not sections[name]:
            sections[name] = "No notable developments reported."

    return sections


# ---------------------------------------------------------------------------
# Stock watchlist: price data + single consolidated LLM call
# ---------------------------------------------------------------------------

def _fetch_stock_price_data(symbols: list[str]) -> dict[str, dict]:
    """Fetch latest close, daily % change, and YTD % change for each ticker."""
    prices: dict[str, dict] = {}
    est = pytz.timezone(config.TIMEZONE)
    year_start = datetime(datetime.now(est).year, 1, 1)

    for symbol in symbols:
        # yfinance uses BRK-B, not BRK.B
        yf_sym = symbol.replace(".", "-")
        try:
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period="5d")
            if hist.empty or len(hist) < 2:
                prices[symbol] = {}
                continue

            close = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[-2]
            day_pct = ((close - prev_close) / prev_close) * 100

            ytd_hist = ticker.history(start=year_start)
            if not ytd_hist.empty and len(ytd_hist) >= 2:
                ytd_pct = ((close - ytd_hist["Close"].iloc[0]) / ytd_hist["Close"].iloc[0]) * 100
            else:
                ytd_pct = None

            prices[symbol] = {
                "close": close,
                "day_pct": day_pct,
                "ytd_pct": ytd_pct,
            }
        except Exception as e:
            print(f"  [yfinance] Error for {symbol}: {e}")
            prices[symbol] = {}

    return prices


def _format_price_line(symbol: str, pdata: dict) -> str:
    """Return a short human-readable price summary for a ticker."""
    if not pdata:
        return f"{symbol}: price unavailable"
    close = pdata["close"]
    day = pdata["day_pct"]
    ytd = pdata.get("ytd_pct")
    day_str = f"{day:+.1f}% day"
    ytd_str = f"{ytd:+.1f}% YTD" if ytd is not None else "YTD N/A"
    return f"{symbol}: ${close:.2f} ({day_str}, {ytd_str})"


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
                        "pageSize": 7,
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
                    f"q={symbol}+stock+earnings&hl=en-US&gl=US&ceid=US:en"
                )
                resp = requests.get(rss_url, timeout=10)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries[:7]:
                    title = entry.get("title", "")
                    headlines.append(f"- {title}")
            except Exception:
                pass

        all_headlines[symbol] = headlines

    return all_headlines


def fetch_stock_news() -> str:
    """Fetch price data and news headlines for the configured stock watchlist."""
    if not config.WATCHLIST_STOCKS:
        return ""

    print("[Stocks] Fetching price data...")
    price_data = _fetch_stock_price_data(config.WATCHLIST_STOCKS)

    print("[Stocks] Fetching headlines...")
    all_headlines = _fetch_all_stock_headlines(config.WATCHLIST_STOCKS)

    if not llm_client.any_llm_configured():
        lines = []
        for sym in config.WATCHLIST_STOCKS:
            price_line = _format_price_line(sym, price_data.get(sym, {}))
            hdls = all_headlines.get(sym, [])
            news_blurb = hdls[0].lstrip("- ") if hdls else "No notable news."
            lines.append(f"{price_line} — {news_blurb}")
        return "📈 Stock Watchlist\n" + "\n".join(lines)

    block_parts = []
    for sym in config.WATCHLIST_STOCKS:
        price_line = _format_price_line(sym, price_data.get(sym, {}))
        hdls = all_headlines.get(sym, [])
        hdl_text = "\n".join(hdls) if hdls else "No headlines found."
        block_parts.append(
            f"[{sym}]\n"
            f"Price: {price_line}\n"
            f"Headlines:\n{hdl_text}"
        )
    combined = "\n\n".join(block_parts)

    prompt = (
        "You are a financial news analyst writing a stock watchlist briefing.\n\n"
        "Below is price performance data and recent headlines for each ticker:\n\n"
        f"{combined}\n\n"
        "STRICT RULES:\n"
        "1. Output one line per ticker in EXACTLY this format:\n"
        "   TICKER ($price, +X.X% day, +X.X% YTD): One sentence of news.\n"
        "   Use the price data provided verbatim — do not alter the numbers.\n"
        "2. The news sentence must describe a specific, meaningful company event: "
        "earnings results (with actual figures), major deals or acquisitions, "
        "regulatory action, analyst rating changes with price targets, executive departures/hires, "
        "or product launches with market impact.\n"
        "3. Always use real names — no 'the company', 'its CEO', or 'the firm'.\n"
        "4. If the headlines contain only opinion pieces, portfolio tips, or generic "
        "market commentary with no concrete company news, write 'No notable company news today.'\n"
        "5. NEVER copy or quote article titles. Rewrite every fact in your own words.\n"
        "6. NEVER attribute to a source ('Seeking Alpha says', 'per CNBC').\n"
        "7. Do NOT add any header, intro, or closing line.\n\n"
        "Begin."
    )

    print(f"  [LLM] Waiting {_BETWEEN_CALLS_DELAY}s before stock call...")
    time.sleep(_BETWEEN_CALLS_DELAY)
    print("  [LLM] Summarizing stock watchlist (1 call)...")
    result = llm_client.complete(prompt)

    if result:
        return "📈 Stock Watchlist\n" + result

    print("  [LLM] All models exhausted — returning price + raw headline fallback.")
    lines = []
    for sym in config.WATCHLIST_STOCKS:
        price_line = _format_price_line(sym, price_data.get(sym, {}))
        hdls = all_headlines.get(sym, [])
        news_blurb = hdls[0].lstrip("- ") if hdls else "No notable news."
        lines.append(f"{price_line} — {news_blurb}")
    return "📈 Stock Watchlist\n" + "\n".join(lines)
