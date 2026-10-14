import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest


# ==========================================================
# LOAD API KEYS
# ==========================================================

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")


# ==========================================================
# CONNECT TO ALPACA NEWS
# ==========================================================

client = NewsClient(
    API_KEY,
    SECRET_KEY
)


# ==========================================================
# STOCKS WE CARE ABOUT
# ==========================================================

symbols = [
    "CRM",
    "NFLX",
    "ADBE",
    "MSFT",
    "CVX",
    "XOM",
    "MA",
    "LLY",
    "V",
    "ORCL",
    "TSLA",
    "NVDA",
    "AMZN",
]


# ==========================================================
# GET RECENT NEWS
# ==========================================================

end = datetime.now(timezone.utc)
start = end - timedelta(hours=24)

request = NewsRequest(
    symbols=",".join(symbols),
    start=start,
    end=end,
    limit=50
)

news = client.get_news(request)


# ==========================================================
# DISPLAY
# ==========================================================

print()
print("======================================================================")
print("                          NEWS BRAIN v0.1")
print("======================================================================")

articles = news.data.get("news", [])

if not articles:
    print("No recent news found.")

else:

    for article in articles:

        created = article.created_at

        related_symbols = ", ".join(
            article.symbols
        )

        print()
        print(
            f"[{created}] "
            f"{related_symbols}"
        )

        print(
            article.headline
        )

        if article.summary:

            summary = article.summary.replace(
                "\n",
                " "
            )

            print(
                f"Summary: {summary}"
            )

        print(
            "-" * 70
        )


print()
print("======================================================================")