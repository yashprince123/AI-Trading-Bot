import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()

client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

account = client.get_account()

print()
print("====================================")
print("ALPACA CONNECTION CHECK")
print("====================================")
print("MODE: PAPER")
print(f"Equity:       ${float(account.equity):,.2f}")
print(f"Cash:         ${float(account.cash):,.2f}")
print(f"Buying power: ${float(account.buying_power):,.2f}")
print(f"Account ID:   {account.id}")
print("====================================")
print("TradingClient was created with paper=True")
print("NO ORDER WAS PLACED")