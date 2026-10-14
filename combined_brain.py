import os
import math
import json
import statistics
import urllib.request
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from alpaca.data.enums import DataFeed, Adjustment
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestQuoteRequest,
    NewsRequest
)
from alpaca.data.timeframe import TimeFrame

from prediction_logger import save_prediction

from news_cache import (
    create_news_cache,
    get_cached_analysis,
    save_cached_analysis
)


# ==========================================================
# SETTINGS
# ==========================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"

STRATEGY_VERSION = "combined_v0.6"

MARKET_WEIGHT = 0.70
NEWS_WEIGHT = 0.30

TOP_STOCKS_FOR_NEWS = 5
ARTICLES_PER_STOCK = 3
NEWS_LOOKBACK_HOURS = 72


# ==========================================================
# LOAD API KEYS
# ==========================================================

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    raise RuntimeError(
        "Alpaca credentials not found in .env"
    )


# ==========================================================
# CLIENTS
# ==========================================================

market_client = StockHistoricalDataClient(
    API_KEY,
    SECRET_KEY
)

news_client = NewsClient(
    API_KEY,
    SECRET_KEY
)


# ==========================================================
# STOCK UNIVERSE
# ==========================================================

symbols = [
    "SPY",
    "QQQ",

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
# HELPERS
# ==========================================================

def clamp(value, minimum, maximum):
    return max(
        minimum,
        min(value, maximum)
    )


# ==========================================================
# MARKET SCORE
# ==========================================================

def calculate_market_score(
    return_5d,
    return_20d,
    relative_strength_20d,
    price,
    sma_20,
    sma_50,
    volume_ratio,
    volatility
):

    score = 50

    # 5-day momentum
    score += clamp(
        return_5d / 0.10,
        -1,
        1
    ) * 10

    # 20-day momentum
    score += clamp(
        return_20d / 0.20,
        -1,
        1
    ) * 15

    # Relative strength vs SPY
    score += clamp(
        relative_strength_20d / 0.15,
        -1,
        1
    ) * 15

    # Trend
    if price > sma_20:
        score += 6
    else:
        score -= 6

    if sma_20 > sma_50:
        score += 5
    else:
        score -= 5

    # Volume confirmation
    if volume_ratio > 1:

        volume_strength = clamp(
            volume_ratio - 1,
            0,
            1.5
        )

        if return_5d > 0:
            score += volume_strength * 6

        elif return_5d < 0:
            score -= volume_strength * 6

    # Volatility adjustment
    if volatility >= 0.70:
        score -= 8

    elif volatility >= 0.50:
        score -= 5

    elif volatility >= 0.35:
        score -= 2

    elif volatility <= 0.20:
        score += 2

    return clamp(
        score,
        0,
        100
    )


# ==========================================================
# BUILD MARKET SCORES
# ==========================================================

def build_market_scores():

    print(
        "Downloading completed daily market data..."
    )

    end = datetime.now(
        timezone.utc
    )

    start = end - timedelta(
        days=120
    )

    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
        adjustment=Adjustment.ALL
    )

    bars = market_client.get_stock_bars(
        request
    )

    today = datetime.now(
        timezone.utc
    ).date()

    completed_data = {}

    for symbol in symbols:

        try:

            stock_bars = bars[
                symbol
            ]

        except Exception:

            continue

        completed_bars = [
            bar
            for bar in stock_bars
            if bar.timestamp.date() < today
        ]

        if len(completed_bars) < 55:
            continue

        completed_data[
            symbol
        ] = completed_bars

    if "SPY" not in completed_data:

        raise RuntimeError(
            "Not enough SPY data."
        )

    # ======================================================
    # SPY BENCHMARK
    # ======================================================

    spy_closes = [
        float(bar.close)
        for bar in completed_data["SPY"]
    ]

    spy_return_20d = (
        spy_closes[-1]
        / spy_closes[-21]
    ) - 1

    results = {}

    # ======================================================
    # ANALYZE EACH SYMBOL
    # ======================================================

    for symbol in symbols:

        if symbol not in completed_data:
            continue

        stock_bars = (
            completed_data[
                symbol
            ]
        )

        closes = [
            float(bar.close)
            for bar in stock_bars
        ]

        volumes = [
            float(bar.volume)
            for bar in stock_bars
        ]

        completed_close = (
            closes[-1]
        )

        # --------------------------------------------------
        # MOMENTUM
        # --------------------------------------------------

        return_5d = (
            completed_close
            / closes[-6]
        ) - 1

        return_20d = (
            completed_close
            / closes[-21]
        ) - 1

        relative_strength_20d = (
            return_20d
            - spy_return_20d
        )

        # --------------------------------------------------
        # MOVING AVERAGES
        # --------------------------------------------------

        sma_20 = (
            sum(closes[-20:])
            / 20
        )

        sma_50 = (
            sum(closes[-50:])
            / 50
        )

        # --------------------------------------------------
        # VOLUME
        # --------------------------------------------------

        latest_volume = (
            volumes[-1]
        )

        average_volume_20 = (
            sum(volumes[-21:-1])
            / 20
        )

        if average_volume_20 > 0:

            volume_ratio = (
                latest_volume
                / average_volume_20
            )

        else:

            volume_ratio = 0

        # --------------------------------------------------
        # VOLATILITY
        # --------------------------------------------------

        recent_closes = (
            closes[-21:]
        )

        daily_returns = []

        for i in range(
            1,
            len(recent_closes)
        ):

            daily_return = (
                recent_closes[i]
                / recent_closes[i - 1]
            ) - 1

            daily_returns.append(
                daily_return
            )

        if len(daily_returns) >= 2:

            daily_volatility = (
                statistics.stdev(
                    daily_returns
                )
            )

            volatility = (
                daily_volatility
                * math.sqrt(252)
            )

        else:

            volatility = 0

        # --------------------------------------------------
        # SCORE
        # --------------------------------------------------

        market_score = (
            calculate_market_score(
                return_5d,
                return_20d,
                relative_strength_20d,
                completed_close,
                sma_20,
                sma_50,
                volume_ratio,
                volatility
            )
        )

        # --------------------------------------------------
        # TREND
        # --------------------------------------------------

        if (
            completed_close > sma_20
            and
            sma_20 > sma_50
        ):

            trend = "STRONG"

        elif completed_close > sma_20:

            trend = "POSITIVE"

        else:

            trend = "WEAK"

        # --------------------------------------------------
        # RISK
        # --------------------------------------------------

        if volatility >= 0.60:

            risk = "HIGH"

        elif volatility >= 0.35:

            risk = "MED"

        else:

            risk = "LOW"

        results[
            symbol
        ] = {

            "market_score":
                market_score,

            "completed_close":
                completed_close,

            "return_5d":
                return_5d,

            "return_20d":
                return_20d,

            "relative_strength_20d":
                relative_strength_20d,

            "volume_ratio":
                volume_ratio,

            "volatility":
                volatility,

            "trend":
                trend,

            "risk":
                risk
        }

    return results


# ==========================================================
# LIVE QUOTE PRICES
# ==========================================================

def get_live_prices(
    market_results
):

    print(
        "Downloading live IEX quotes..."
    )

    request = (
        StockLatestQuoteRequest(
            symbol_or_symbols=symbols,
            feed=DataFeed.IEX
        )
    )

    quotes = (
        market_client
        .get_stock_latest_quote(
            request
        )
    )

    live_prices = {}

    for symbol in symbols:

        fallback_price = None

        if symbol in market_results:

            fallback_price = (
                market_results[
                    symbol
                ][
                    "completed_close"
                ]
            )

        try:

            quote = quotes[
                symbol
            ]

            bid = float(
                quote.bid_price
            )

            ask = float(
                quote.ask_price
            )

            if (
                bid > 0
                and
                ask > 0
            ):

                price = (
                    bid + ask
                ) / 2

            elif ask > 0:

                price = ask

            elif bid > 0:

                price = bid

            else:

                price = (
                    fallback_price
                )

        except Exception:

            price = (
                fallback_price
            )

        if price is not None:

            live_prices[
                symbol
            ] = price

    return live_prices


# ==========================================================
# QWEN ANALYSIS
# ==========================================================

def ask_qwen(
    ticker,
    headline,
    summary
):

    prompt = f"""
You are a financial-news analysis engine.

Analyze this article ONLY for its likely impact on {ticker}.

TICKER:
{ticker}

HEADLINE:
{headline}

SUMMARY:
{summary}

Return ONLY valid JSON:

{{
    "sentiment": "neutral",
    "sentiment_score": 0.0,
    "importance": 1,
    "relevance": 1,
    "time_horizon": "days",
    "event_type": "other",
    "reason": "brief explanation"
}}

sentiment must be:
bullish
bearish
neutral

sentiment_score:
-1.0 to 1.0

importance:
integer from 1 to 10

relevance:
integer from 1 to 10

time_horizon:
intraday
days
weeks
months

event_type:
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

Rules:

- Analyze specifically how the article affects {ticker}.
- Do not assume every tagged ticker is important.
- Ignore clickbait.
- Do not invent facts.
- Generic commentary should receive low relevance.
- Earnings and guidance may be highly important.
- Major regulation, lawsuits, acquisitions,
  financing, products or management changes
  may be important.
- Output JSON only.
"""

    payload = {

        "model":
            MODEL,

        "messages": [
            {
                "role":
                    "user",

                "content":
                    prompt
            }
        ],

        "stream":
            False,

        "think":
            False,

        "format":
            "json",

        "options": {

            "temperature":
                0,

            "seed":
                42
        }
    }

    request = (
        urllib.request.Request(
            OLLAMA_URL,

            data=json.dumps(
                payload
            ).encode(
                "utf-8"
            ),

            headers={
                "Content-Type":
                    "application/json"
            },

            method=
                "POST"
        )
    )

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:

        result = json.loads(
            response
            .read()
            .decode(
                "utf-8"
            )
        )

    content = (
        result[
            "message"
        ][
            "content"
        ]
    )

    return json.loads(
        content
    )


# ==========================================================
# CACHED AI ANALYSIS
# ==========================================================

def analyze_news_for_ticker(
    ticker,
    headline,
    summary
):

    # ------------------------------------------------------
    # CHECK CACHE FIRST
    # ------------------------------------------------------

    cached = (
        get_cached_analysis(
            ticker,
            headline,
            summary
        )
    )

    if cached is not None:

        return (
            cached,
            True
        )

    # ------------------------------------------------------
    # NOT CACHED — ASK QWEN
    # ------------------------------------------------------

    analysis = (
        ask_qwen(
            ticker,
            headline,
            summary
        )
    )

    # ------------------------------------------------------
    # CLEAN OUTPUT
    # ------------------------------------------------------

    analysis[
        "sentiment_score"
    ] = clamp(
        float(
            analysis.get(
                "sentiment_score",
                0
            )
        ),
        -1,
        1
    )

    analysis[
        "importance"
    ] = int(
        clamp(
            int(
                analysis.get(
                    "importance",
                    1
                )
            ),
            1,
            10
        )
    )

    analysis[
        "relevance"
    ] = int(
        clamp(
            int(
                analysis.get(
                    "relevance",
                    1
                )
            ),
            1,
            10
        )
    )

    # ------------------------------------------------------
    # STORE ANALYSIS IN CACHE
    # ------------------------------------------------------

    save_cached_analysis(
        ticker,
        headline,
        summary,
        analysis,
        MODEL
    )

    return (
        analysis,
        False
    )


# ==========================================================
# GET COMPANY NEWS
# ==========================================================

def get_targeted_news(
    ticker
):

    end = datetime.now(
        timezone.utc
    )

    start = end - timedelta(
        hours=NEWS_LOOKBACK_HOURS
    )

    request = NewsRequest(
        symbols=ticker,
        start=start,
        end=end,
        limit=ARTICLES_PER_STOCK
    )

    response = (
        news_client
        .get_news(
            request
        )
    )

    return (
        response.data.get(
            "news",
            []
        )
    )


# ==========================================================
# BUILD COMPANY NEWS SCORE
# ==========================================================

def build_targeted_news_score(
    ticker
):

    print()

    print(
        f"Searching news for "
        f"{ticker}..."
    )

    articles = (
        get_targeted_news(
            ticker
        )
    )

    if not articles:

        print(
            "  No recent news found."
        )

        return {

            "news_score":
                50.0,

            "news_count":
                0,

            "top_headline":
                "",

            "top_reason":
                ""
        }

    impacts = []

    analyzed_articles = []

    for article in articles:

        headline = (
            article.headline
        )

        summary = (
            article.summary
            if article.summary
            else
            "No summary provided."
        )

        print(
            f"  Article: "
            f"{headline}"
        )

        try:

            analysis, was_cached = (
                analyze_news_for_ticker(
                    ticker,
                    headline,
                    summary
                )
            )

            if was_cached:

                print(
                    "    Source: CACHE"
                )

            else:

                print(
                    "    Source: QWEN"
                )

            sentiment_score = clamp(
                float(
                    analysis.get(
                        "sentiment_score",
                        0
                    )
                ),
                -1,
                1
            )

            importance = int(
                clamp(
                    int(
                        analysis.get(
                            "importance",
                            1
                        )
                    ),
                    1,
                    10
                )
            )

            relevance = int(
                clamp(
                    int(
                        analysis.get(
                            "relevance",
                            1
                        )
                    ),
                    1,
                    10
                )
            )

            impact = (
                sentiment_score
                * (
                    importance / 10
                )
                * (
                    relevance / 10
                )
            )

            impacts.append(
                impact
            )

            analyzed_articles.append({

                "headline":
                    headline,

                "impact":
                    impact,

                "reason":
                    analysis.get(
                        "reason",
                        ""
                    )
            })

            print(
                f"    Sentiment: "
                f"{analysis.get('sentiment')}"
            )

            print(
                f"    Score: "
                f"{sentiment_score:+.2f}"
            )

            print(
                f"    Importance: "
                f"{importance}/10"
            )

            print(
                f"    Relevance: "
                f"{relevance}/10"
            )

            print(
                f"    Impact: "
                f"{impact:+.3f}"
            )

        except Exception as error:

            print(
                f"    AI ERROR: "
                f"{error}"
            )

    if not impacts:

        return {

            "news_score":
                50.0,

            "news_count":
                0,

            "top_headline":
                "",

            "top_reason":
                ""
        }

    total_impact = clamp(
        sum(
            impacts
        ),
        -1,
        1
    )

    news_score = (
        50
        +
        total_impact * 50
    )

    top_article = max(
        analyzed_articles,
        key=lambda item:
            abs(
                item[
                    "impact"
                ]
            )
    )

    return {

        "news_score":
            news_score,

        "news_count":
            len(
                analyzed_articles
            ),

        "top_headline":
            top_article[
                "headline"
            ],

        "top_reason":
            top_article[
                "reason"
            ]
    }


# ==========================================================
# START
# ==========================================================

print()

print(
    "=============================================================="
)

print(
    "                COMBINED BRAIN v0.6"
)

print(
    "=============================================================="
)

print(
    f"Strategy version: {STRATEGY_VERSION}"
)


# ==========================================================
# MAKE SURE CACHE EXISTS
# ==========================================================

create_news_cache()


# ==========================================================
# MARKET DATA
# ==========================================================

market_results = (
    build_market_scores()
)


# ==========================================================
# LIVE PRICES
# ==========================================================

live_prices = (
    get_live_prices(
        market_results
    )
)


# ==========================================================
# FIND BEST MARKET CANDIDATES
# ==========================================================

individual_stocks = [

    symbol

    for symbol
    in symbols

    if symbol not in [
        "SPY",
        "QQQ"
    ]

    and

    symbol in market_results
]


individual_stocks.sort(
    key=lambda ticker:
        market_results[
            ticker
        ][
            "market_score"
        ],
    reverse=True
)


news_targets = (
    individual_stocks[
        :TOP_STOCKS_FOR_NEWS
    ]
)


print()

print(
    "Top stocks selected "
    "for AI news research:"
)

print(
    ", ".join(
        news_targets
    )
)


# ==========================================================
# NEWS RESEARCH
# ==========================================================

news_results = {}


for ticker in news_targets:

    news_results[
        ticker
    ] = (
        build_targeted_news_score(
            ticker
        )
    )


# ==========================================================
# COMBINE MARKET + NEWS
# ==========================================================

combined_results = []


for symbol in symbols:

    if symbol not in market_results:
        continue

    market = (
        market_results[
            symbol
        ]
    )

    news = (
        news_results.get(
            symbol,
            {
                "news_score":
                    50.0,

                "news_count":
                    0,

                "top_headline":
                    "",

                "top_reason":
                    ""
            }
        )
    )

    market_score = (
        market[
            "market_score"
        ]
    )

    news_score = (
        news[
            "news_score"
        ]
    )

    conviction = (
        market_score
        * MARKET_WEIGHT
        +
        news_score
        * NEWS_WEIGHT
    )

    prediction_price = (
        live_prices.get(
            symbol,
            market[
                "completed_close"
            ]
        )
    )

    combined_results.append({

        "symbol":
            symbol,

        "prediction_price":
            prediction_price,

        "completed_close":
            market[
                "completed_close"
            ],

        "conviction":
            conviction,

        "market_score":
            market_score,

        "news_score":
            news_score,

        "news_count":
            news[
                "news_count"
            ],

        "return_5d":
            market[
                "return_5d"
            ],

        "return_20d":
            market[
                "return_20d"
            ],

        "relative_strength_20d":
            market[
                "relative_strength_20d"
            ],

        "volatility":
            market[
                "volatility"
            ],

        "risk":
            market[
                "risk"
            ],

        "trend":
            market[
                "trend"
            ],

        "top_headline":
            news[
                "top_headline"
            ],

        "top_reason":
            news[
                "top_reason"
            ]
    })


combined_results.sort(
    key=lambda item:
        item[
            "conviction"
        ],
    reverse=True
)


# ==========================================================
# FINAL TABLE
# ==========================================================

print()
print()

print(
    "================================================================================================"
)

print(
    "                           FINAL CONVICTION RANKING"
)

print(
    "================================================================================================"
)

print(
    f"{'Rank':<6}"
    f"{'Ticker':<8}"
    f"{'LivePx':<11}"
    f"{'Conv':<8}"
    f"{'Market':<9}"
    f"{'News':<8}"
    f"{'#News':<8}"
    f"{'5D':<9}"
    f"{'20D':<9}"
    f"{'RS20':<9}"
    f"{'Risk':<7}"
    f"{'Trend':<10}"
)

print(
    "------------------------------------------------------------------------------------------------"
)


for rank, stock in enumerate(
    combined_results,
    start=1
):

    print(
        f"{rank:<6}"
        f"{stock['symbol']:<8}"
        f"${stock['prediction_price']:<10.2f}"
        f"{stock['conviction']:<8.1f}"
        f"{stock['market_score']:<9.1f}"
        f"{stock['news_score']:<8.1f}"
        f"{stock['news_count']:<8}"
        f"{stock['return_5d']:<9.2%}"
        f"{stock['return_20d']:<9.2%}"
        f"{stock['relative_strength_20d']:<9.2%}"
        f"{stock['risk']:<7}"
        f"{stock['trend']:<10}"
    )


print(
    "================================================================================================"
)


# ==========================================================
# TOP CANDIDATES
# ==========================================================

print()

print(
    "TOP CANDIDATES"
)

print(
    "--------------------------------------------------------------"
)


for stock in combined_results[:5]:

    print()

    print(
        f"{stock['symbol']} | "
        f"Conviction: "
        f"{stock['conviction']:.1f}"
    )

    print(
        f"Live prediction price: "
        f"${stock['prediction_price']:.2f}"
    )

    print(
        f"Previous completed close: "
        f"${stock['completed_close']:.2f}"
    )

    print(
        f"Market: "
        f"{stock['market_score']:.1f} | "
        f"News: "
        f"{stock['news_score']:.1f}"
    )

    print(
        f"Risk: "
        f"{stock['risk']} | "
        f"Trend: "
        f"{stock['trend']}"
    )

    if stock[
        "top_headline"
    ]:

        print(
            f"Top news: "
            f"{stock['top_headline']}"
        )

        print(
            f"AI reason: "
            f"{stock['top_reason']}"
        )

    else:

        print(
            "No targeted news analyzed."
        )


# ==========================================================
# SAVE PREDICTIONS
# ==========================================================

print()

print(
    "Saving predictions using "
    "live quote prices..."
)

print(
    f"Strategy tag: "
    f"{STRATEGY_VERSION}"
)


saved_count = 0
skipped_count = 0


for stock in combined_results:

    try:

        was_saved = save_prediction(

            ticker=
                stock[
                    "symbol"
                ],

            price=
                stock[
                    "prediction_price"
                ],

            conviction=
                stock[
                    "conviction"
                ],

            market_score=
                stock[
                    "market_score"
                ],

            news_score=
                stock[
                    "news_score"
                ],

            return_5d=
                stock[
                    "return_5d"
                ],

            return_20d=
                stock[
                    "return_20d"
                ],

            relative_strength_20d=
                stock[
                    "relative_strength_20d"
                ],

            volatility=
                stock[
                    "volatility"
                ],

            risk=
                stock[
                    "risk"
                ],

            trend=
                stock[
                    "trend"
                ],

            news_count=
                stock[
                    "news_count"
                ],

            strategy_version=
                STRATEGY_VERSION
        )


        if was_saved:

            saved_count += 1

        else:

            skipped_count += 1


    except Exception as error:

        print(
            f"Database error for "
            f"{stock['symbol']}: "
            f"{error}"
        )


print()

print(
    f"Saved new predictions: "
    f"{saved_count}"
)

print(
    f"Skipped existing daily snapshots: "
    f"{skipped_count}"
)