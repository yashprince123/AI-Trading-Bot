from datetime import datetime

from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy
from lumibot.entities import Asset


class DualMomentumStrategy(Strategy):

    def initialize(self):
        self.sleeptime = "1D"

        self.vars.last_rebalance_month = ""
        self.vars.pending_target = ""

        # Assets we compare for growth
        self.vars.risk_assets = ["QQQ", "SPY"]

        # Where we hide when momentum is negative
        self.vars.safe_asset = "IEF"

    def get_asset(self, symbol):
        return Asset(symbol, asset_type=Asset.AssetType.STOCK)

    def get_12_month_return(self, symbol):
        asset = self.get_asset(symbol)

        bars = self.get_historical_prices(
            asset,
            253,
            "day",
            timeshift=1
        )

        if bars is None or bars.df.empty:
            return None

        closes = bars.df["close"].dropna()

        if len(closes) < 252:
            return None

        start_price = float(closes.iloc[-252])
        end_price = float(closes.iloc[-1])

        return (end_price / start_price) - 1

    def buy_target(self, symbol):
        asset = self.get_asset(symbol)

        position = self.get_position(asset)

        if position is not None and float(position.quantity) > 0:
            self.vars.pending_target = ""
            return

        price = self.get_last_price(asset)

        if price is None:
            return

        cash = float(self.get_cash())

        # Keep a small cash buffer
        quantity = int((cash * 0.95) / float(price))

        if quantity <= 0:
            return

        order = self.create_order(
            asset,
            quantity,
            "buy"
        )

        self.submit_order(order)

        self.log_message(
            f"BUY {quantity} shares of {symbol}"
        )

        self.vars.pending_target = ""

    def sell_everything_except(self, target_symbol):
        positions = self.get_positions()

        sold_something = False

        for position in positions:

            symbol = position.asset.symbol

            if symbol == target_symbol:
                continue

            if float(position.quantity) > 0:

                order = self.create_order(
                    position.asset,
                    position.quantity,
                    "sell"
                )

                self.submit_order(order)

                self.log_message(
                    f"SELL {position.quantity} shares of {symbol}"
                )

                sold_something = True

        return sold_something

    def on_trading_iteration(self):

        # ------------------------------
        # Finish a pending asset switch
        # ------------------------------

        if self.vars.pending_target:

            positions = self.get_positions()

            remaining_positions = [
                p for p in positions
                if float(p.quantity) > 0
                and p.asset.symbol != self.vars.pending_target
            ]

            if remaining_positions:
                return

            self.buy_target(self.vars.pending_target)
            return

        # ------------------------------
        # Rebalance monthly
        # ------------------------------

        now = self.get_datetime()
        month_key = now.strftime("%Y-%m")

        if self.vars.last_rebalance_month == month_key:
            return

        # First trading week of each month
        if now.day > 7:
            return

        returns = {}

        for symbol in self.vars.risk_assets:

            momentum = self.get_12_month_return(symbol)

            if momentum is None:
                return

            returns[symbol] = momentum

        # Pick whichever risky asset performed best
        best_symbol = max(
            returns,
            key=returns.get
        )

        best_return = returns[best_symbol]

        # Absolute momentum filter:
        # If even the winner has negative 12-month momentum,
        # move defensive.
        if best_return > 0:
            target_symbol = best_symbol
        else:
            target_symbol = self.vars.safe_asset

        self.log_message(
            f"{now.date()} | "
            f"QQQ: {returns['QQQ']:.2%} | "
            f"SPY: {returns['SPY']:.2%} | "
            f"TARGET: {target_symbol}"
        )

        self.vars.last_rebalance_month = month_key

        target_asset = self.get_asset(target_symbol)
        target_position = self.get_position(target_asset)

        # Already holding what we want
        if (
            target_position is not None
            and float(target_position.quantity) > 0
        ):
            return

        # Sell previous holding first
        sold = self.sell_everything_except(target_symbol)

        if sold:
            self.vars.pending_target = target_symbol
            return

        # Starting from cash
        self.buy_target(target_symbol)


if __name__ == "__main__":

    results = DualMomentumStrategy.backtest(
        YahooDataBacktesting,
        datetime(2012, 1, 1),
        datetime(2026, 8, 1),
        benchmark_asset="SPY",
    )

    print()
    print("================================")
    print("DUAL MOMENTUM BACKTEST FINISHED")
    print("================================")

    print(f"CAGR:         {results['cagr']:.2%}")
    print(f"Total Return: {results['total_return']:.2%}")
    print(f"Sharpe:       {results['sharpe']:.2f}")

    max_dd = results["max_drawdown"]["drawdown"]

    print(f"Max Drawdown: {-max_dd:.2%}")