import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest


# ==========================================================
# SETTINGS
# ==========================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"

MAX_ARTICLES = 5


# ==========================================================
# LOAD API KEYS
# ==========================================================

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")


# ==========================================================
# ALPACA NEWS CLIENT
# ==========================================================

news_client = NewsClient(
    API_KEY,
    SECRET_KEY
)


# ==========================================================
# STOCK UNIVERSE
# ==========================================================

symbols = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "AMD",
    "NFLX",
    "JPM",
    "V",
    "MA",
    "WMT",
    "COST",
    "LLY",
    "UNH",
    "XOM",
    "CVX",
    "CRM",
    "ORCL",
    "ADBE",
    "INTC",
]


# ==========================================================
# LOCAL AI ANALYSIS
# ==========================================================

def analyze_news_for_ticker(
    ticker,
    headline,
    summary
):

    prompt = f"""
You are a financial-news analysis engine.

Analyze the impact of this article specifically on:

TICKER: {ticker}

Headline:
{headline}

Summary:
{summary}

Do NOT score the overall article.

Score only how this article affects {ticker}.

Return ONLY valid JSON:

{{
    "ticker": "{ticker}",
    "sentiment": "neutral",
    "sentiment_score": 0.0,
    "importance": 1,
    "relevance": 1,
    "time_horizon": "days",
    "event_type": "other",
    "reason": "brief explanation"
}}

Rules:

sentiment must be:
bullish
bearish
neutral

sentiment_score:
-1.0 = extremely bearish
0.0 = neutral
1.0 = extremely bullish

importance:
1 to 10
How market-moving the event could be.

relevance:
1 to 10
How directly this article relates to {ticker}.

time_horizon must be:
intraday
days
weeks
months

event_type must be:
earnings
analyst
regulation
product
acquisition
macro
legal
recall
management
competition
financing
other

Important rules:

- A ticker merely being mentioned does NOT make the article relevant.
- Generic market articles should receive low relevance unless
  they have a clear direct impact on {ticker}.
- Analyst rating changes can be relevant but are usually not
  extremely important.
- Earnings, guidance, major regulation, recalls, acquisitions,
  lawsuits, and major product developments can be highly important.
- Ignore clickbait.
- Do not invent facts.
- Do not output markdown.
- Output JSON only.
"""

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "think": False,
        "format": "json"
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:

        result = json.loads(
            response.read().decode("utf-8")
        )

    content = result["message"]["content"]

    return json.loads(content)


# ==========================================================
# GET RECENT NEWS
# ==========================================================

end = datetime.now(timezone.utc)
start = end - timedelta(hours=24)

request = NewsRequest(
    symbols=",".join(symbols),
    start=start,
    end=end,
    limit=MAX_ARTICLES
)

news_response = news_client.get_news(
    request
)

articles = news_response.data.get(
    "news",
    []
)


# ==========================================================
# DISPLAY ANALYSIS
# ==========================================================

print()
print(
    "======================================================================"
)
print(
    "                 LIVE AI NEWS BRAIN v0.3"
)
print(
    "======================================================================"
)


if not articles:
    print("No recent articles found.")


for number, article in enumerate(
    articles,
    start=1
):

    headline = article.headline

    summary = (
        article.summary
        if article.summary
        else "No summary provided."
    )

    # Only analyze symbols that are actually
    # part of our trading universe.
    relevant_symbols = [
        symbol
        for symbol in article.symbols
        if symbol in symbols
    ]

    if not relevant_symbols:
        continue

    print()
    print(f"ARTICLE {number}")
    print(f"Headline: {headline}")
    print("-" * 70)

    for ticker in relevant_symbols:

        print()
        print(
            f"Analyzing {ticker}..."
        )

        try:

            analysis = analyze_news_for_ticker(
                ticker,
                headline,
                summary
            )

            print(
                f"Ticker:      "
                f"{analysis['ticker']}"
            )

            print(
                f"Sentiment:   "
                f"{analysis['sentiment']}"
            )

            print(
                f"Score:       "
                f"{analysis['sentiment_score']}"
            )

            print(
                f"Importance:  "
                f"{analysis['importance']}/10"
            )

            print(
                f"Relevance:   "
                f"{analysis['relevance']}/10"
            )

            print(
                f"Horizon:     "
                f"{analysis['time_horizon']}"
            )

            print(
                f"Event:       "
                f"{analysis['event_type']}"
            )

            print(
                f"Reason:      "
                f"{analysis['reason']}"
            )

        except Exception as error:

            print(
                f"AI analysis failed: {error}"
            )

        print("-" * 40)


print()
print(
    "======================================================================"
)
print(
    "NEWS ANALYSIS COMPLETE"
)
print(
    "======================================================================"
)