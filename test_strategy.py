print("SCRIPT STARTED")

from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy
from datetime import datetime

from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy


class TestStrategy(Strategy):

    def on_trading_iteration(self):
        if self.first_iteration:
            price = self.get_last_price("SPY")
            quantity = int(self.portfolio_value // price)

            order = self.create_order(
                "SPY",
                quantity,
                "buy"
            )

            self.submit_order(order)


results = TestStrategy.backtest(
    YahooDataBacktesting,
    datetime(2024, 1, 1),
    datetime(2025, 1, 1),
    benchmark_asset="SPY",
)

print("\nBACKTEST FINISHED")
print(results)