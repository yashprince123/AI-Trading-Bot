from datetime import datetime

from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy
from lumibot.entities import Asset


class DailyProtectedDualMomentum(Strategy):

    def initialize(self):
        self.sleeptime = "1D"

        self.vars.last_rebalance_month = ""
        self.vars.pending_target = ""

        self.vars.risk_assets = ["QQQ", "SPY"]
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

        previous_close = float(closes.iloc[-1])
        year_ago = float(closes.iloc[-252])

        return_12m = (
            previous_close / year_ago
        ) - 1

        sma_200 = float(
            closes.tail(200).mean()
        )

        return {
            "price": previous_close,
            "return_12m": return_12m,
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
            f"BUY {quantity} {symbol}"
        )

        self.vars.pending_target = ""

    def switch_to(self, target_symbol):
        target_asset = self.get_asset(
            target_symbol
        )

        target_position = self.get_position(
            target_asset
        )

        # Already holding only the correct asset
        other_positions = [
            p for p in self.get_positions()
            if float(p.quantity) > 0
            and p.asset.symbol != target_symbol
        ]

        if (
            target_position is not None
            and float(target_position.quantity) > 0
            and not other_positions
        ):
            return

        sold_something = False

        for position in other_positions:

            order = self.create_order(
                position.asset,
                position.quantity,
                "sell"
            )

            self.submit_order(order)

            self.log_message(
                f"SELL {position.quantity} "
                f"{position.asset.symbol}"
            )

            sold_something = True

        if sold_something:
            self.vars.pending_target = (
                target_symbol
            )
            return

        self.buy_target(target_symbol)

    def get_current_risk_position(self):
        for position in self.get_positions():

            if (
                position.asset.symbol
                in self.vars.risk_assets
                and float(position.quantity) > 0
            ):
                return position

        return None

    def on_trading_iteration(self):

        now = self.get_datetime()

        # ==================================
        # FINISH PREVIOUS ASSET SWITCH
        # ==================================

        if self.vars.pending_target:

            target = self.vars.pending_target

            remaining = [
                p for p in self.get_positions()
                if float(p.quantity) > 0
                and p.asset.symbol != target
            ]

            if remaining:
                return

            self.buy_target(target)
            return

        # ==================================
        # DAILY EMERGENCY PROTECTION
        # ==================================

        risk_position = (
            self.get_current_risk_position()
        )

        if risk_position is not None:

            symbol = risk_position.asset.symbol
            metrics = self.get_metrics(symbol)

            if metrics is not None:

                if (
                    metrics["price"]
                    < metrics["sma_200"]
                ):
                    self.log_message(
                        f"{now.date()} | "
                        f"DAILY RISK EXIT | "
                        f"{symbol} close "
                        f"${metrics['price']:.2f} "
                        f"< SMA200 "
                        f"${metrics['sma_200']:.2f}"
                    )

                    self.switch_to(
                        self.vars.safe_asset
                    )

                    return

        # ==================================
        # MONTHLY MOMENTUM SELECTION
        # ==================================

        month_key = now.strftime("%Y-%m")

        if (
            self.vars.last_rebalance_month
            == month_key
        ):
            return

        # Rebalance during first trading week
        if now.day > 7:
            return

        data = {}

        for symbol in self.vars.risk_assets:

            metrics = self.get_metrics(symbol)

            if metrics is None:
                return

            data[symbol] = metrics

        best_symbol = max(
            self.vars.risk_assets,
            key=lambda symbol:
                data[symbol]["return_12m"]
        )

        best = data[best_symbol]

        # Require:
        # 1. Positive 12-month momentum
        # 2. Price above 200-day trend
        if (
            best["return_12m"] > 0
            and best["price"] > best["sma_200"]
        ):
            target_symbol = best_symbol

        else:
            target_symbol = (
                self.vars.safe_asset
            )

        self.log_message(
            f"{now.date()} | "
            f"MONTHLY | "
            f"QQQ: "
            f"{data['QQQ']['return_12m']:.2%} | "
            f"SPY: "
            f"{data['SPY']['return_12m']:.2%} | "
            f"TARGET: {target_symbol}"
        )

        self.vars.last_rebalance_month = (
            month_key
        )

        self.switch_to(target_symbol)


if __name__ == "__main__":

    results = (
        DailyProtectedDualMomentum.backtest(
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
        "DAILY PROTECTED RESULTS"
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
        f"Max Drawdown: "
        f"{-max_dd:.2%}"
    )