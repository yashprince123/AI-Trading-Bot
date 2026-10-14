import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus


load_dotenv()

client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

after = (
    datetime.now(timezone.utc)
    - timedelta(days=1)
)

request = GetOrdersRequest(
    status=QueryOrderStatus.ALL,
    after=after
)

orders = client.get_orders(
    filter=request
)

print()
print("==============================================")
print("RECENT ALPACA PAPER ORDERS")
print("==============================================")

if not orders:
    print("No recent orders.")

for order in orders:

    print()
    print(f"Symbol:          {order.symbol}")
    print(f"Side:            {order.side}")
    print(f"Status:          {order.status}")
    print(f"Notional:        {order.notional}")
    print(f"Qty:             {order.qty}")
    print(f"Filled qty:      {order.filled_qty}")
    print(f"Filled avg price:{order.filled_avg_price}")
    print(f"Submitted at:    {order.submitted_at}")
    print(f"Client order ID: {order.client_order_id}")

print()
print("==============================================")