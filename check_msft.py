import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from alpaca.data.enums import DataFeed, Adjustment
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


load_dotenv()

client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY")
)

end = datetime.now(timezone.utc)
start = end - timedelta(days=60)

request = StockBarsRequest(
    symbol_or_symbols="MSFT",
    timeframe=TimeFrame.Day,
    start=start,
    end=end,
    feed=DataFeed.IEX,
    adjustment=Adjustment.ALL
)

bars = client.get_stock_bars(request)["MSFT"]

print()
print("LAST MSFT DAILY BARS")
print("--------------------")

for bar in bars[-25:]:
    print(
        bar.timestamp.date(),
        f"${float(bar.close):.2f}"
    )

closes = [float(bar.close) for bar in bars]

if len(closes) >= 21:
    return_20d = closes[-1] / closes[-21] - 1

    print()
    print(f"20-day return: {return_20d:.2%}")