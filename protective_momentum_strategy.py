from datetime import datetime

from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy
from lumibot.entities import Asset


class ProtectiveMomentumStrategy(Strategy):

    def initialize(self):
        self.sleeptime = "1D"

        self.vars.last_rebalance_month = ""
        self.vars.pending_target = ""

        # Growth candidates
        self.vars.risk_assets = ["QQQ", "SPY"]

        # Ultra-short Treasury bills
        self.vars.safe_asset = "BIL"

    def get_asset(self, symbol):
        return Asset(
            symbol,
            asset_type=Asset.AssetType.STOCK
        )

    def get_metrics(self, symbol):
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

        current_price = float(closes.iloc[-1])
        year_ago_price = float(closes.iloc[-252])

        return_12m = (
            current_price / year_ago_price
        ) - 1

        sma_200 = float(
            closes.tail(200).mean()
        )

        return {
            "return_12m": return_12m,
            "price": current_price,
            "sma_200": sma_200
        }

    def buy_target(self, symbol):
        asset = self.get_asset(symbol)

        position = self.get_position(asset)

        if (
            position is not None
            and float(position.quantity) > 0
        ):
            self.vars.pending_target = ""
            return

        price = self.get_last_price(asset)

        if price is None:
            return

        cash = float(self.get_cash())
        price = float(price)

        # Keep 5% cash buffer
        quantity = int(
            (cash * 0.95) / price
        )

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
        sold_something = False

        for position in self.get_positions():

            if position.asset.symbol == target_symbol:
                continue

            if float(position.quantity) <= 0:
                continue

            order = self.create_order(
                position.asset,
                position.quantity,
                "sell"
            )

            self.submit_order(order)

            self.log_message(
                f"SELL {position.quantity} shares of "
                f"{position.asset.symbol}"
            )

            sold_something = True

        return sold_something

    def on_trading_iteration(self):

        # -----------------------------------
        # Finish a switch from the prior day
        # -----------------------------------

        if self.vars.pending_target:

            remaining = [
                p for p in self.get_positions()
                if float(p.quantity) > 0
                and p.asset.symbol
                != self.vars.pending_target
            ]

            if remaining:
                return

            self.buy_target(
                self.vars.pending_target
            )

            return

        # -----------------------------------
        # Rebalance once per month
        # -----------------------------------

        now = self.get_datetime()
        month_key = now.strftime("%Y-%m")

        if (
            self.vars.last_rebalance_month
            == month_key
        ):
            return

        # Use first trading week
        if now.day > 7:
            return

        data = {}

        for symbol in self.vars.risk_assets:

            metrics = self.get_metrics(symbol)

            if metrics is None:
                return

            data[symbol] = metrics

        # -----------------------------------
        # Relative momentum
        # -----------------------------------

        best_symbol = max(
            self.vars.risk_assets,
            key=lambda s:
                data[s]["return_12m"]
        )

        best = data[best_symbol]

        # -----------------------------------
        # Protective filters
        # -----------------------------------

        positive_momentum = (
            best["return_12m"] > 0
        )

        above_200_sma = (
            best["price"] > best["sma_200"]
        )

        if (
            positive_momentum
            and above_200_sma
        ):
            target_symbol = best_symbol
            status = "RISK ON"

        else:
            target_symbol = (
                self.vars.safe_asset
            )
            status = "DEFENSIVE"

        self.log_message(
            f"{now.date()} | "
            f"QQQ 12M: "
            f"{data['QQQ']['return_12m']:.2%} | "
            f"SPY 12M: "
            f"{data['SPY']['return_12m']:.2%} | "
            f"Winner: {best_symbol} | "
            f"Price: ${best['price']:.2f} | "
            f"SMA200: ${best['sma_200']:.2f} | "
            f"{status} -> {target_symbol}"
        )

        self.vars.last_rebalance_month = (
            month_key
        )

        target_asset = self.get_asset(
            target_symbol
        )

        target_position = self.get_position(
            target_asset
        )

        # Already positioned correctly
        if (
            target_position is not None
            and float(
                target_position.quantity
            ) > 0
        ):
            return

        # Sell previous holding
        sold = self.sell_everything_except(
            target_symbol
        )

        if sold:

            self.vars.pending_target = (
                target_symbol
            )

            return

        # Starting from cash
        self.buy_target(target_symbol)


if __name__ == "__main__":

    results = (
        ProtectiveMomentumStrategy.backtest(
            YahooDataBacktesting,
            datetime(2012, 1, 1),
            datetime(2026, 8, 1),
            benchmark_asset="SPY",
        )
    )

    print()
    print(
        "================================"
    )
    print(
        "PROTECTIVE MOMENTUM RESULTS"
    )
    print(
        "================================"
    )

    print(
        f"CAGR:         "
        f"{results['cagr']:.2%}"
    )

    print(
        f"Total Return: "
        f"{results['total_return']:.2%}"
    )

    print(
        f"Sharpe:       "
        f"{results['sharpe']:.2f}"
    )

    max_dd = (
        results["max_drawdown"]["drawdown"]
    )

    print(
        f"Max Drawdown: {-max_dd:.2%}"
    )