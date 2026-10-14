import os
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

from risk_engine import (
    evaluate_new_position
)

from diversification_engine import (
    build_exposure_state,
    apply_diversification_limits,
    add_exposure
)


# ==========================================================
# SETTINGS
# ==========================================================

DATABASE = "trading_brain.db"

STRATEGY_VERSION = "combined_v0.6"

MARKET_TIMEZONE = ZoneInfo(
    "America/New_York"
)

NON_STOCK_SYMBOLS = {
    "SPY",
    "QQQ"
}


# ==========================================================
# LOAD ALPACA KEYS
# ==========================================================

load_dotenv()

API_KEY = os.getenv(
    "ALPACA_API_KEY"
)

SECRET_KEY = os.getenv(
    "ALPACA_SECRET_KEY"
)

if not API_KEY or not SECRET_KEY:

    raise RuntimeError(
        "Alpaca credentials not found in .env"
    )


# ==========================================================
# PAPER TRADING CLIENT
# ==========================================================

trading_client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True
)


# ==========================================================
# CURRENT MARKET DATE
# ==========================================================

def get_market_date():

    now = datetime.now(
        timezone.utc
    )

    return now.astimezone(
        MARKET_TIMEZONE
    ).date()


# ==========================================================
# LOAD TODAY'S LATEST STRATEGY PREDICTIONS
# ==========================================================

def get_latest_predictions():

    market_date = (
        get_market_date()
    )


    connection = sqlite3.connect(
        DATABASE
    )

    connection.row_factory = (
        sqlite3.Row
    )

    cursor = connection.cursor()


    cursor.execute(
        """
        SELECT
            id,
            timestamp,
            ticker,
            price,
            conviction,
            market_score,
            news_score,
            volatility,
            risk,
            trend,
            strategy_version

        FROM predictions

        WHERE strategy_version = ?

        ORDER BY timestamp DESC
        """,
        (
            STRATEGY_VERSION,
        )
    )


    rows = cursor.fetchall()

    connection.close()


    today_rows = []

    seen_tickers = set()


    for row in rows:

        try:

            prediction_time = (
                datetime.fromisoformat(
                    row[
                        "timestamp"
                    ]
                )
            )


            if prediction_time.tzinfo is None:

                prediction_time = (
                    prediction_time.replace(
                        tzinfo=timezone.utc
                    )
                )


            prediction_date = (
                prediction_time.astimezone(
                    MARKET_TIMEZONE
                ).date()
            )


        except Exception:

            continue


        if prediction_date != market_date:

            continue


        ticker = row[
            "ticker"
        ]


        # Keep only latest row per ticker.
        if ticker in seen_tickers:

            continue


        seen_tickers.add(
            ticker
        )


        today_rows.append(
            dict(
                row
            )
        )


    today_rows.sort(
        key=lambda row:
            row[
                "conviction"
            ],
        reverse=True
    )


    return today_rows


# ==========================================================
# LOAD CURRENT PAPER ACCOUNT
# ==========================================================

def get_account_state():

    account = (
        trading_client.get_account()
    )


    positions = (
        trading_client.get_all_positions()
    )


    equity = float(
        account.equity
    )


    cash = float(
        account.cash
    )


    current_exposure = sum(

        abs(
            float(
                position.market_value
            )
        )

        for position
        in positions
    )


    held_symbols = {

        position.symbol

        for position
        in positions
    }


    return {

        "equity":
            equity,

        "cash":
            cash,

        "current_exposure":
            current_exposure,

        "positions":
            positions,

        "open_positions_count":
            len(
                positions
            ),

        "held_symbols":
            held_symbols
    }


# ==========================================================
# BUILD DYNAMIC TRADE PLAN
# ==========================================================

def build_trade_plan(
    predictions,
    account_state,
    market_regime_multiplier=1.0
):

    # ------------------------------------------------------
    # Simulated account state
    #
    # Every approved proposed trade changes the state
    # seen by the next stock.
    # ------------------------------------------------------

    simulated_cash = (
        account_state[
            "cash"
        ]
    )


    simulated_exposure = (
        account_state[
            "current_exposure"
        ]
    )


    held_symbols = set(
        account_state[
            "held_symbols"
        ]
    )


    # ------------------------------------------------------
    # Diversification state begins with actual holdings.
    # ------------------------------------------------------

    diversification_state = (
        build_exposure_state(
            account_state[
                "positions"
            ]
        )
    )


    trade_plan = []

    rejected = []


    # ======================================================
    # PROCESS STOCKS FROM HIGHEST CONVICTION DOWN
    # ======================================================

    for prediction in predictions:

        ticker = str(
            prediction[
                "ticker"
            ]
        ).upper()


        conviction = float(
            prediction[
                "conviction"
            ]
        )


        risk = str(
            prediction[
                "risk"
            ]
        ).upper()


        # ==================================================
        # BENCHMARK ETFs ARE NOT INDIVIDUAL STOCK TRADES
        # ==================================================

        if ticker in NON_STOCK_SYMBOLS:

            continue


        # ==================================================
        # EXISTING POSITION
        #
        # Existing holdings are handled by
        # portfolio_manager / sell executor.
        #
        # This planner only creates NEW positions.
        # ==================================================

        if ticker in held_symbols:

            rejected.append({

                "ticker":
                    ticker,

                "conviction":
                    conviction,

                "reason":
                    "Already held. Existing position "
                    "is managed by Portfolio Manager."
            })

            continue


        # ==================================================
        # STEP 1 — DYNAMIC RISK ENGINE
        #
        # Determines how much this stock DESERVES
        # based on:
        #
        # conviction
        # stock risk
        # market regime
        # cash
        # total portfolio exposure
        #
        # No fixed stock-count limit.
        # ==================================================

        risk_result = (
            evaluate_new_position(

                ticker=
                    ticker,

                conviction=
                    conviction,

                risk=
                    risk,

                account_equity=
                    account_state[
                        "equity"
                    ],

                cash=
                    simulated_cash,

                current_exposure=
                    simulated_exposure,

                open_positions_count=
                    None,

                market_regime_multiplier=
                    market_regime_multiplier
            )
        )


        if not risk_result[
            "allowed"
        ]:

            rejected.append({

                "ticker":
                    ticker,

                "conviction":
                    conviction,

                "reason":
                    "; ".join(
                        risk_result[
                            "reasons"
                        ]
                    )
            })

            continue


        proposed_notional = float(
            risk_result[
                "target_notional"
            ]
        )


        if proposed_notional <= 0:

            continue


        # ==================================================
        # STEP 2 — DIVERSIFICATION ENGINE
        #
        # Risk engine says how much the stock deserves.
        #
        # Diversification engine may REDUCE that amount
        # if the portfolio already has too much exposure
        # to its sector/theme.
        # ==================================================

        diversification_result = (
            apply_diversification_limits(

                ticker=
                    ticker,

                proposed_notional=
                    proposed_notional,

                account_equity=
                    account_state[
                        "equity"
                    ],

                exposure_state=
                    diversification_state
            )
        )


        if not diversification_result[
            "allowed"
        ]:

            rejected.append({

                "ticker":
                    ticker,

                "conviction":
                    conviction,

                "reason":
                    "; ".join(
                        diversification_result[
                            "reasons"
                        ]
                    )
            })

            continue


        final_notional = float(
            diversification_result[
                "adjusted_notional"
            ]
        )


        if final_notional <= 0:

            continue


        # ==================================================
        # SAVE APPROVED TRADE
        # ==================================================

        trade = {

            "ticker":
                ticker,

            "conviction":
                conviction,

            "risk":
                risk,

            "price":
                float(
                    prediction[
                        "price"
                    ]
                ),

            # Final amount that may actually
            # reach the order executor.
            "notional":
                round(
                    final_notional,
                    2
                ),

            # Useful diagnostics.
            "base_allocation_percent":
                risk_result[
                    "base_allocation_percent"
                ],

            "risk_multiplier":
                risk_result[
                    "risk_multiplier"
                ],

            "market_regime_multiplier":
                risk_result[
                    "market_regime_multiplier"
                ],

            "target_allocation_percent":
                risk_result[
                    "final_allocation_percent"
                ],

            "pre_diversification_notional":
                proposed_notional,

            "sector":
                diversification_result[
                    "sector"
                ],

            "clusters":
                diversification_result[
                    "clusters"
                ],

            "diversification_reasons":
                diversification_result[
                    "reasons"
                ]
        }


        trade_plan.append(
            trade
        )


        # ==================================================
        # UPDATE SIMULATED ACCOUNT
        #
        # The next candidate sees this proposed trade as
        # already committed.
        # ==================================================

        simulated_cash -= (
            final_notional
        )


        simulated_exposure += (
            final_notional
        )


        held_symbols.add(
            ticker
        )


        # ==================================================
        # UPDATE DIVERSIFICATION EXPOSURE
        # ==================================================

        add_exposure(

            diversification_state,

            ticker,

            final_notional
        )


    return (
        trade_plan,
        rejected
    )


# ==========================================================
# DISPLAY TRADE
# ==========================================================

def print_trade(
    number,
    trade
):

    estimated_shares = (

        trade[
            "notional"
        ]

        /

        trade[
            "price"
        ]
    )


    print()
    print(
        f"{number}. "
        f"{trade['ticker']}"
    )


    print(
        f"   Conviction: "
        f"{trade['conviction']:.1f}"
    )


    print(
        f"   Risk: "
        f"{trade['risk']}"
    )


    print(
        f"   Sector: "
        f"{trade['sector']}"
    )


    clusters = (
        ", ".join(
            trade[
                "clusters"
            ]
        )
        if trade[
            "clusters"
        ]
        else "NONE"
    )


    print(
        f"   Clusters: "
        f"{clusters}"
    )


    print()
    print(
        "   Dynamic sizing:"
    )


    print(
        f"     Base allocation: "
        f"{trade['base_allocation_percent'] * 100:.2f}%"
    )


    print(
        f"     Risk multiplier: "
        f"{trade['risk_multiplier']:.2f}x"
    )


    print(
        f"     Market multiplier: "
        f"{trade['market_regime_multiplier']:.2f}x"
    )


    print(
        f"     Target allocation: "
        f"{trade['target_allocation_percent'] * 100:.2f}%"
    )


    print()
    print(
        f"   Pre-diversification target: "
        f"${trade['pre_diversification_notional']:,.2f}"
    )


    print(
        f"   Final proposed order: "
        f"${trade['notional']:,.2f}"
    )


    print(
        f"   Reference price: "
        f"${trade['price']:.2f}"
    )


    print(
        f"   Approx shares: "
        f"{estimated_shares:.3f}"
    )


    print(
        "   Action: BUY"
    )


    for reason in trade[
        "diversification_reasons"
    ]:

        print(
            f"   Diversification: "
            f"{reason}"
        )


# ==========================================================
# MAIN
# ==========================================================

def main():

    print()
    print(
        "=============================================================="
    )

    print(
        "              PAPER TRADE PLANNER v0.2"
    )

    print(
        "=============================================================="
    )

    print(
        "DYNAMIC POSITION SIZING"
    )

    print(
        "SECTOR / THEME DIVERSIFICATION"
    )

    print(
        "NO FIXED NUMBER OF STOCKS"
    )

    print(
        "DRY RUN ONLY"
    )

    print(
        "THIS SCRIPT CANNOT PLACE ORDERS"
    )


    # ======================================================
    # LOAD PREDICTIONS
    # ======================================================

    predictions = (
        get_latest_predictions()
    )


    if not predictions:

        print()
        print(
            "No predictions found for "
            "today's market date."
        )

        return


    print()
    print(
        f"Predictions loaded: "
        f"{len(predictions)}"
    )


    # ======================================================
    # ACCOUNT
    # ======================================================

    account_state = (
        get_account_state()
    )


    print()
    print(
        "PAPER ACCOUNT"
    )

    print(
        "--------------------------------------------------------------"
    )


    print(
        f"Equity: "
        f"${account_state['equity']:,.2f}"
    )


    print(
        f"Cash: "
        f"${account_state['cash']:,.2f}"
    )


    print(
        f"Current exposure: "
        f"${account_state['current_exposure']:,.2f}"
    )


    exposure_percent = (

        account_state[
            "current_exposure"
        ]

        /

        account_state[
            "equity"
        ]

        * 100
    )


    print(
        f"Current exposure %: "
        f"{exposure_percent:.2f}%"
    )


    print(
        f"Current holdings: "
        f"{account_state['open_positions_count']}"
    )


    # ======================================================
    # PLAN
    #
    # Market regime is currently neutral/normal = 1.00.
    #
    # We'll replace this with an actual regime model next.
    # ======================================================

    market_regime_multiplier = 1.00


    trade_plan, rejected = (
        build_trade_plan(

            predictions=
                predictions,

            account_state=
                account_state,

            market_regime_multiplier=
                market_regime_multiplier
        )
    )


    # ======================================================
    # APPROVED TRADES
    # ======================================================

    print()
    print(
        "=============================================================="
    )

    print(
        "                  PROPOSED PAPER ORDERS"
    )

    print(
        "=============================================================="
    )


    if not trade_plan:

        print()
        print(
            "NO NEW TRADES PROPOSED"
        )


    for number, trade in enumerate(
        trade_plan,
        start=1
    ):

        print_trade(
            number,
            trade
        )


    total_notional = sum(

        trade[
            "notional"
        ]

        for trade
        in trade_plan
    )


    projected_exposure = (

        account_state[
            "current_exposure"
        ]

        + total_notional
    )


    projected_exposure_percent = (

        projected_exposure

        /

        account_state[
            "equity"
        ]

        * 100
    )


    projected_cash = (

        account_state[
            "cash"
        ]

        - total_notional
    )


    print()
    print(
        "--------------------------------------------------------------"
    )


    print(
        f"Proposed new trades: "
        f"{len(trade_plan)}"
    )


    print(
        f"New capital proposed: "
        f"${total_notional:,.2f}"
    )


    print(
        f"Projected exposure: "
        f"${projected_exposure:,.2f} "
        f"({projected_exposure_percent:.2f}%)"
    )


    print(
        f"Projected cash: "
        f"${projected_cash:,.2f}"
    )


    # ======================================================
    # REJECTIONS
    # ======================================================

    print()
    print(
        "TOP REJECTIONS"
    )

    print(
        "--------------------------------------------------------------"
    )


    for rejection in rejected[
        :12
    ]:

        conviction = (
            rejection.get(
                "conviction"
            )
        )


        if conviction is not None:

            print(
                f"{rejection['ticker']} "
                f"({conviction:.1f}): "
                f"{rejection['reason']}"
            )


        else:

            print(
                f"{rejection['ticker']}: "
                f"{rejection['reason']}"
            )


    print()
    print(
        "=============================================================="
    )

    print(
        "DRY RUN COMPLETE — ZERO ORDERS SUBMITTED"
    )

    print(
        "=============================================================="
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    main()