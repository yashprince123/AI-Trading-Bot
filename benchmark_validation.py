from datetime import datetime

from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies import Strategy
from lumibot.entities import Asset

from dual_momentum_strategy import DualMomentumStrategy


# ============================================================
# BUY AND HOLD STRATEGIES
# ============================================================

class SPYBuyAndHold(Strategy):

    def initialize(self):
        self.sleeptime = "1D"

    def on_trading_iteration(self):

        if not self.first_iteration:
            return

        asset = Asset(
            "SPY",
            asset_type=Asset.AssetType.STOCK
        )

        price = self.get_last_price(asset)

        if price is None:
            return

        cash = float(self.get_cash())

        quantity = int(
            (cash * 0.99) / float(price)
        )

        if quantity <= 0:
            return

        order = self.create_order(
            asset,
            quantity,
            "buy"
        )

        self.submit_order(order)


class QQQBuyAndHold(Strategy):

    def initialize(self):
        self.sleeptime = "1D"

    def on_trading_iteration(self):

        if not self.first_iteration:
            return

        asset = Asset(
            "QQQ",
            asset_type=Asset.AssetType.STOCK
        )

        price = self.get_last_price(asset)

        if price is None:
            return

        cash = float(self.get_cash())

        quantity = int(
            (cash * 0.99) / float(price)
        )

        if quantity <= 0:
            return

        order = self.create_order(
            asset,
            quantity,
            "buy"
        )

        self.submit_order(order)


# ============================================================
# TEST PERIODS
# ============================================================

TEST_PERIODS = [
    (
        "Full history",
        datetime(2008, 1, 1),
        datetime(2026, 8, 1)
    ),
    (
        "2008-2012",
        datetime(2008, 1, 1),
        datetime(2012, 12, 31)
    ),
    (
        "2013-2019",
        datetime(2013, 1, 1),
        datetime(2019, 12, 31)
    ),
    (
        "2020-2022",
        datetime(2020, 1, 1),
        datetime(2022, 12, 31)
    ),
    (
        "2023-2026",
        datetime(2023, 1, 1),
        datetime(2026, 8, 1)
    ),
]


# ============================================================
# RUN ONE BACKTEST
# ============================================================

def run_strategy(strategy, start, end):

    results = strategy.backtest(
        YahooDataBacktesting,
        start,
        end,
        show_plot=False,
        show_tearsheet=False,
        show_indicators=False,
        save_tearsheet=False,
    )

    return {
        "cagr": float(results["cagr"]),
        "total_return": float(
            results["total_return"]
        ),
        "sharpe": float(
            results["sharpe"]
        ),
        "max_drawdown": float(
            results["max_drawdown"]["drawdown"]
        ),
    }


# ============================================================
# RUN VALIDATION
# ============================================================

all_results = []


for period_name, start, end in TEST_PERIODS:

    print()
    print("========================================")
    print(f"TESTING: {period_name}")
    print("========================================")

    print("Running Dual Momentum...")

    dual = run_strategy(
        DualMomentumStrategy,
        start,
        end
    )

    print("Running SPY Buy & Hold...")

    spy = run_strategy(
        SPYBuyAndHold,
        start,
        end
    )

    print("Running QQQ Buy & Hold...")

    qqq = run_strategy(
        QQQBuyAndHold,
        start,
        end
    )

    all_results.append({
        "period": period_name,
        "dual": dual,
        "spy": spy,
        "qqq": qqq
    })


# ============================================================
# PRINT RESULTS
# ============================================================

print()
print()
print(
    "=============================================================="
)
print(
    "              STRATEGY VS BUY-AND-HOLD"
)
print(
    "=============================================================="
)


for result in all_results:

    print()
    print(
        "--------------------------------------------------------------"
    )

    print(
        result["period"]
    )

    print(
        "--------------------------------------------------------------"
    )

    print(
        f"{'Strategy':<18}"
        f"{'CAGR':>10}"
        f"{'Return':>12}"
        f"{'Sharpe':>10}"
        f"{'Max DD':>12}"
    )

    print(
        f"{'Dual Momentum':<18}"
        f"{result['dual']['cagr']:>9.2%}"
        f"{result['dual']['total_return']:>11.2%}"
        f"{result['dual']['sharpe']:>10.2f}"
        f"{-result['dual']['max_drawdown']:>11.2%}"
    )

    print(
        f"{'SPY Buy & Hold':<18}"
        f"{result['spy']['cagr']:>9.2%}"
        f"{result['spy']['total_return']:>11.2%}"
        f"{result['spy']['sharpe']:>10.2f}"
        f"{-result['spy']['max_drawdown']:>11.2%}"
    )

    print(
        f"{'QQQ Buy & Hold':<18}"
        f"{result['qqq']['cagr']:>9.2%}"
        f"{result['qqq']['total_return']:>11.2%}"
        f"{result['qqq']['sharpe']:>10.2f}"
        f"{-result['qqq']['max_drawdown']:>11.2%}"
    )


print()
print(
    "=============================================================="
)
print(
    "BENCHMARK VALIDATION COMPLETE"
)
print(
    "=============================================================="
)