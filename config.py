import os
from dotenv import load_dotenv

load_dotenv()


# --- API Keys ---
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Delivery targets ---
USER_PHONE = os.getenv("USER_PHONE", "")
USER_CARRIER = os.getenv("USER_CARRIER", "")
USER_EMAIL = os.getenv("USER_EMAIL", "")
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# --- Schedule ---
SEND_TIME = os.getenv("SEND_TIME", "07:00")
TIMEZONE = "US/Eastern"

# --- News topics and summary lengths (user-editable) ---
NEWS_TOPICS = {
    "Economic & Financial": {
        "query": "economy OR finance OR stock market OR Wall Street",
        "length": "1 paragraph (4-5 sentences)",
        "category": "business",
    },
    "Geopolitics": {
        "query": "geopolitics OR diplomacy OR international relations OR war",
        "length": "2-3 sentences max",
        "category": "general",
    },
    "General News": {
        "query": "breaking news",
        "length": "2-3 sentences max",
        "category": "general",
    },
    "Technology": {
        "query": "technology OR AI OR software OR silicon valley",
        "length": "1 paragraph (4-5 sentences)",
        "category": "technology",
    },
}

# --- Stock watchlist (user-editable) ---
WATCHLIST_STOCKS = ["COF", "AXP", "AMZN", "BRK.B", "COST", "GOOGL", "NFLX", "SPOT", "XOM"]

# --- Sports teams to track ---
SPORTS_TEAMS = [
    {"name": "Oakland Athletics", "sport": "baseball", "espn_slug": "mlb", "espn_id": "11"},
    {"name": "New York Mets", "sport": "baseball", "espn_slug": "mlb", "espn_id": "21"},
    {"name": "Las Vegas Raiders", "sport": "football", "espn_slug": "nfl", "espn_id": "13"},
    {"name": "Sacramento Kings", "sport": "basketball", "espn_slug": "nba", "espn_id": "23"},
    {"name": "Los Angeles Lakers", "sport": "basketball", "espn_slug": "nba", "espn_id": "13"},
    {"name": "Real Madrid", "sport": "soccer", "espn_slug": "esp.1", "espn_id": "86"},
    {"name": "Formula 1", "sport": "racing", "espn_slug": "f1", "espn_id": None},
]
