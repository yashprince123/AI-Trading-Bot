import os
import math
import statistics
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from alpaca.data.enums import DataFeed, Adjustment
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


# ==========================================================
# LOAD API KEYS
# ==========================================================

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

client = StockHistoricalDataClient(
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
# DOWNLOAD DAILY MARKET DATA
# ==========================================================

end = datetime.now(timezone.utc)
start = end - timedelta(days=120)

request = StockBarsRequest(
    symbol_or_symbols=symbols,
    timeframe=TimeFrame.Day,
    start=start,
    end=end,
    feed=DataFeed.IEX,
    adjustment=Adjustment.ALL
)

bars = client.get_stock_bars(request)


# ==========================================================
# HELPERS
# ==========================================================

def clamp(value, minimum, maximum):
    return max(
        minimum,
        min(value, maximum)
    )


def calculate_score(
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

    # ------------------------------------------------------
    # SHORT-TERM MOMENTUM
    # Max influence: +/- 10 points
    # ------------------------------------------------------

    score += clamp(
        return_5d / 0.10,
        -1,
        1
    ) * 10

    # ------------------------------------------------------
    # 20-DAY MOMENTUM
    # Max influence: +/- 15 points
    # ------------------------------------------------------

    score += clamp(
        return_20d / 0.20,
        -1,
        1
    ) * 15

    # ------------------------------------------------------
    # RELATIVE STRENGTH VS SPY
    # Max influence: +/- 15 points
    # ------------------------------------------------------

    score += clamp(
        relative_strength_20d / 0.15,
        -1,
        1
    ) * 15

    # ------------------------------------------------------
    # PRICE TREND
    # ------------------------------------------------------

    if price > sma_20:
        score += 6
    else:
        score -= 6

    if sma_20 > sma_50:
        score += 5
    else:
        score -= 5

    # ------------------------------------------------------
    # VOLUME CONFIRMATION
    # ------------------------------------------------------

    if volume_ratio > 1:

        volume_strength = clamp(
            volume_ratio - 1,
            0,
            1.5
        )

        # High volume confirms positive momentum
        if return_5d > 0:
            score += volume_strength * 6

        # High volume confirms negative momentum
        elif return_5d < 0:
            score -= volume_strength * 6

    # ------------------------------------------------------
    # VOLATILITY PENALTY
    # ------------------------------------------------------

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
# REMOVE TODAY'S INCOMPLETE DAILY BAR
# ==========================================================

today = datetime.now(timezone.utc).date()

completed_data = {}

for symbol in symbols:

    stock_bars = bars[symbol]

    completed_bars = [
        bar
        for bar in stock_bars
        if bar.timestamp.date() < today
    ]

    if len(completed_bars) < 55:
        continue

    completed_data[symbol] = completed_bars


# ==========================================================
# CALCULATE SPY BENCHMARK RETURN
# ==========================================================

spy_bars = completed_data["SPY"]

spy_closes = [
    float(bar.close)
    for bar in spy_bars
]

spy_return_20d = (
    spy_closes[-1]
    / spy_closes[-21]
) - 1


# ==========================================================
# ANALYZE EACH STOCK
# ==========================================================

results = []


for symbol in symbols:

    if symbol not in completed_data:
        continue

    stock_bars = completed_data[symbol]

    closes = [
        float(bar.close)
        for bar in stock_bars
    ]

    volumes = [
        float(bar.volume)
        for bar in stock_bars
    ]

    price = closes[-1]

    # ------------------------------------------------------
    # MOMENTUM
    # ------------------------------------------------------

    return_5d = (
        price / closes[-6]
    ) - 1

    return_20d = (
        price / closes[-21]
    ) - 1

    # ------------------------------------------------------
    # RELATIVE STRENGTH VS SPY
    # ------------------------------------------------------

    relative_strength_20d = (
        return_20d
        - spy_return_20d
    )

    # ------------------------------------------------------
    # MOVING AVERAGES
    # ------------------------------------------------------

    sma_20 = (
        sum(closes[-20:])
        / 20
    )

    sma_50 = (
        sum(closes[-50:])
        / 50
    )

    # ------------------------------------------------------
    # VOLUME RATIO
    # ------------------------------------------------------

    latest_volume = volumes[-1]

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

    # ------------------------------------------------------
    # 20-DAY ANNUALIZED VOLATILITY
    # ------------------------------------------------------

    recent_closes = closes[-21:]

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

    # ------------------------------------------------------
    # OPPORTUNITY SCORE
    # ------------------------------------------------------

    score = calculate_score(
        return_5d,
        return_20d,
        relative_strength_20d,
        price,
        sma_20,
        sma_50,
        volume_ratio,
        volatility
    )

    # ------------------------------------------------------
    # TREND LABEL
    # ------------------------------------------------------

    if (
        price > sma_20
        and sma_20 > sma_50
    ):

        trend = "STRONG"

    elif price > sma_20:

        trend = "POSITIVE"

    else:

        trend = "WEAK"

    # ------------------------------------------------------
    # RISK LABEL
    # ------------------------------------------------------

    if volatility >= 0.60:

        risk = "HIGH"

    elif volatility >= 0.35:

        risk = "MED"

    else:

        risk = "LOW"

    # ------------------------------------------------------
    # SAVE RESULT
    # ------------------------------------------------------

    results.append({
        "symbol": symbol,
        "score": score,
        "return_5d": return_5d,
        "return_20d": return_20d,
        "relative_strength_20d":
            relative_strength_20d,
        "volume_ratio": volume_ratio,
        "volatility": volatility,
        "risk": risk,
        "trend": trend
    })


# ==========================================================
# SORT BY OPPORTUNITY SCORE
# ==========================================================

results.sort(
    key=lambda x: x["score"],
    reverse=True
)


# ==========================================================
# DISPLAY RESULTS
# ==========================================================

print()

print(
    "========================================================================================"
)

print(
    "                               MARKET BRAIN v0.7"
)

print(
    "========================================================================================"
)

print(
    f"{'Rank':<6}"
    f"{'Ticker':<8}"
    f"{'Score':<8}"
    f"{'5D':<10}"
    f"{'20D':<10}"
    f"{'RS20':<10}"
    f"{'Volume':<9}"
    f"{'Vol':<9}"
    f"{'Risk':<7}"
    f"{'Trend':<12}"
)

print(
    "----------------------------------------------------------------------------------------"
)


for rank, stock in enumerate(
    results,
    start=1
):

    print(
        f"{rank:<6}"
        f"{stock['symbol']:<8}"
        f"{stock['score']:<8.1f}"
        f"{stock['return_5d']:<10.2%}"
        f"{stock['return_20d']:<10.2%}"
        f"{stock['relative_strength_20d']:<10.2%}"
        f"{stock['volume_ratio']:<9.2f}"
        f"{stock['volatility']:<9.1%}"
        f"{stock['risk']:<7}"
        f"{stock['trend']:<12}"
    )


print(
    "========================================================================================"
)

print(
    f"SPY 20-day benchmark return: "
    f"{spy_return_20d:.2%}"
)