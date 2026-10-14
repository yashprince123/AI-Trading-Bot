from datetime import datetime

from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy
from lumibot.entities import Asset


class TrendMomentumStrategy(Strategy):

    def initialize(self):
        # Run once per trading day
        self.sleeptime = "1D"

        # Store strategy state
        self.vars.last_rebalance_month = ""
        self.vars.pending_target = ""

        self.vars.risk_symbol = "QQQ"
        self.vars.safe_symbol = "IEF"

    def get_stock(self, symbol):
        return Asset(
            symbol,
            asset_type=Asset.AssetType.STOCK
        )

    def buy_target(self, symbol):
        asset = self.get_stock(symbol)

        # Don't buy it again if we already own it
        position = self.get_position(asset)

        if position is not None and float(position.quantity) > 0:
            self.vars.pending_target = ""
            return

        price = self.get_last_price(asset)

        if price is None:
            self.log_message(f"No price available for {symbol}")
            return

        cash = float(self.get_cash())
        price = float(price)

        # Use 95% instead of 100% so we leave a cash buffer
        quantity = int((cash * 0.95) / price)

        if quantity <= 0:
            return

        order = self.create_order(
            asset,
            quantity,
            "buy"
        )

        self.submit_order(order)

        self.log_message(
            f"BUY {quantity} shares of {symbol} at approximately ${price:.2f}"
        )

        self.vars.pending_target = ""

    def on_trading_iteration(self):

        # --------------------------------------------------
        # FINISH A SWITCH THAT STARTED YESTERDAY
        # --------------------------------------------------

        if self.vars.pending_target:

            target_symbol = self.vars.pending_target

            if target_symbol == self.vars.risk_symbol:
                other_symbol = self.vars.safe_symbol
            else:
                other_symbol = self.vars.risk_symbol

            other_asset = self.get_stock(other_symbol)
            other_position = self.get_position(other_asset)

            # Wait for yesterday's sell order to finish
            if (
                other_position is not None
                and float(other_position.quantity) > 0
            ):
                return

            self.buy_target(target_symbol)
            return

        # --------------------------------------------------
        # ONLY REBALANCE ONCE PER MONTH
        # --------------------------------------------------

        now = self.get_datetime()
        month_key = now.strftime("%Y-%m")

        if self.vars.last_rebalance_month == month_key:
            return

        # Use the first trading day within roughly
        # the first week of each month
        if now.day > 7:
            return

        risk_asset = self.get_stock(self.vars.risk_symbol)

        # Get the previous 200 COMPLETED daily bars.
        # timeshift=1 prevents us from using today's unfinished bar.
        bars = self.get_historical_prices(
            risk_asset,
            200,
            "day",
            timeshift=1
        )

        if bars is None or bars.df.empty:
            self.log_message("Historical data unavailable")
            return

        closes = bars.df["close"].dropna()

        if len(closes) < 200:
            self.log_message("Not enough historical data yet")
            return

        previous_close = float(closes.iloc[-1])
        sma_200 = float(closes.tail(200).mean())

        # --------------------------------------------------
        # THE ACTUAL STRATEGY
        # --------------------------------------------------

        if previous_close > sma_200:
            target_symbol = self.vars.risk_symbol
            signal = "RISK ON"
        else:
            target_symbol = self.vars.safe_symbol
            signal = "DEFENSIVE"

        self.log_message(
            f"{now.date()} | "
            f"QQQ: ${previous_close:.2f} | "
            f"200-day SMA: ${sma_200:.2f} | "
            f"{signal} -> {target_symbol}"
        )

        self.vars.last_rebalance_month = month_key

        target_asset = self.get_stock(target_symbol)

        if target_symbol == self.vars.risk_symbol:
            other_symbol = self.vars.safe_symbol
        else:
            other_symbol = self.vars.risk_symbol

        other_asset = self.get_stock(other_symbol)

        target_position = self.get_position(target_asset)
        other_position = self.get_position(other_asset)

        # Already holding the correct asset
        if (
            target_position is not None
            and float(target_position.quantity) > 0
            and (
                other_position is None
                or float(other_position.quantity) <= 0
            )
        ):
            return

        # Need to sell the old asset first
        if (
            other_position is not None
            and float(other_position.quantity) > 0
        ):

            sell_order = self.create_order(
                other_position.asset,
                other_position.quantity,
                "sell"
            )

            self.submit_order(sell_order)

            self.log_message(
                f"SELL {other_position.quantity} shares of {other_symbol}"
            )

            # Buy the new asset after the sell fills
            self.vars.pending_target = target_symbol
            return

        # Starting with cash: buy target immediately
        self.buy_target(target_symbol)


if __name__ == "__main__":

    results = TrendMomentumStrategy.backtest(
        YahooDataBacktesting,
        datetime(2012, 1, 1),
        datetime(2026, 8, 1),
        benchmark_asset="SPY",
    )

    print()
    print("================================")
    print("BACKTEST FINISHED")
    print("================================")
    print(results)