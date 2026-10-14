from datetime import datetime

from lumibot.backtesting import YahooDataBacktesting

from dual_momentum_strategy import DualMomentumStrategy


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


def run_test(name, start, end):

    print()
    print("========================================")
    print(f"RUNNING: {name}")
    print(f"{start.date()} -> {end.date()}")
    print("========================================")

    results = DualMomentumStrategy.backtest(
        YahooDataBacktesting,
        start,
        end,
        benchmark_asset="SPY",

        # Disable browser windows / charts
        show_plot=False,
        show_tearsheet=False,
        show_indicators=False,
        save_tearsheet=False,
    )

    max_dd = results["max_drawdown"]["drawdown"]

    return {
        "name": name,
        "cagr": float(results["cagr"]),
        "total_return": float(results["total_return"]),
        "sharpe": float(results["sharpe"]),
        "max_drawdown": float(max_dd),
    }


all_results = []


for name, start, end in TEST_PERIODS:

    try:

        result = run_test(
            name,
            start,
            end
        )

        all_results.append(result)

    except Exception as error:

        print()
        print(f"ERROR during {name}:")
        print(error)

        all_results.append({
            "name": name,
            "cagr": None,
            "total_return": None,
            "sharpe": None,
            "max_drawdown": None,
        })


print()
print()
print("====================================================================")
print("                    DUAL MOMENTUM VALIDATION")
print("====================================================================")

print(
    f"{'Period':<18}"
    f"{'CAGR':>12}"
    f"{'Return':>14}"
    f"{'Sharpe':>12}"
    f"{'Max DD':>14}"
)

print("--------------------------------------------------------------------")


for result in all_results:

    if result["cagr"] is None:

        print(
            f"{result['name']:<18}"
            f"{'ERROR':>12}"
            f"{'ERROR':>14}"
            f"{'ERROR':>12}"
            f"{'ERROR':>14}"
        )

        continue

    print(
        f"{result['name']:<18}"
        f"{result['cagr']:>11.2%}"
        f"{result['total_return']:>13.2%}"
        f"{result['sharpe']:>12.2f}"
        f"{-result['max_drawdown']:>13.2%}"
    )


print("====================================================================")
print()
print("VALIDATION COMPLETE")