import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import (
    OrderSide,
    TimeInForce
)

from paper_trade_planner import (
    get_latest_predictions,
    get_account_state,
    build_trade_plan
)

from risk_engine import (
    MIN_CASH_RESERVE_PERCENT,
    validate_long_only_positions
)


# ==========================================================
# SETTINGS
# ==========================================================

# True = submit ALPACA PAPER orders.
#
# IMPORTANT:
# TradingClient below is still hard-coded to paper=True.
#
# This does NOT enable live-money trading.
EXECUTE_PAPER_ORDERS = False

STRATEGY_VERSION = "combined_v0.6"

SNAPSHOT_MINUTES_BEFORE_CLOSE = 15

SNAPSHOT_TOLERANCE_MINUTES = 5

MARKET_TIMEZONE = ZoneInfo(
    "America/New_York"
)


# ==========================================================
# LOAD API KEYS
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
# ALPACA PAPER CLIENT
#
# CRITICAL:
# paper=True is hard-coded.
# ==========================================================

trading_client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True
)


# ==========================================================
# CLIENT ORDER ID
# ==========================================================

def build_client_order_id(
    ticker
):

    market_date = (
        datetime.now(
            timezone.utc
        )
        .astimezone(
            MARKET_TIMEZONE
        )
        .strftime(
            "%Y%m%d"
        )
    )

    return (
        f"aiv06-"
        f"{market_date}-"
        f"{ticker.lower()}-buy"
    )


# ==========================================================
# PARSE PREDICTION TIMESTAMP
# ==========================================================

def parse_prediction_time(
    timestamp_text
):

    value = datetime.fromisoformat(
        timestamp_text
    )

    if value.tzinfo is None:

        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        MARKET_TIMEZONE
    )


# ==========================================================
# VERIFY OFFICIAL SNAPSHOT
# ==========================================================

def validate_snapshot(
    predictions,
    clock
):

    if not predictions:

        return (
            False,
            "No predictions loaded."
        )


    market_close = (
        clock.next_close
        .astimezone(
            MARKET_TIMEZONE
        )
    )


    official_snapshot = (
        market_close
        - timedelta(
            minutes=
                SNAPSHOT_MINUTES_BEFORE_CLOSE
        )
    )


    earliest_allowed = (
        official_snapshot
        - timedelta(
            minutes=
                SNAPSHOT_TOLERANCE_MINUTES
        )
    )


    latest_allowed = (
        market_close
    )


    prediction_times = []


    for prediction in predictions:

        try:

            prediction_time = (
                parse_prediction_time(
                    prediction[
                        "timestamp"
                    ]
                )
            )

            prediction_times.append(
                prediction_time
            )

        except Exception:

            return (
                False,
                "A prediction has an invalid timestamp."
            )


    earliest_prediction = min(
        prediction_times
    )

    latest_prediction = max(
        prediction_times
    )


    print()
    print(
        "OFFICIAL SNAPSHOT CHECK"
    )

    print(
        "--------------------------------------------------------------"
    )

    print(
        f"Official snapshot: "
        f"{official_snapshot}"
    )

    print(
        f"Earliest accepted: "
        f"{earliest_allowed}"
    )

    print(
        f"Earliest prediction: "
        f"{earliest_prediction}"
    )

    print(
        f"Latest prediction: "
        f"{latest_prediction}"
    )


    if earliest_prediction < earliest_allowed:

        return (
            False,
            "Today's predictions were created "
            "before the official snapshot window."
        )


    if latest_prediction > latest_allowed:

        return (
            False,
            "Prediction timestamp is later "
            "than today's market close."
        )


    return (
        True,
        "Prediction batch passes official snapshot check."
    )


# ==========================================================
# DISPLAY TRADE
# ==========================================================

def print_trade(
    number,
    trade
):

    estimated_shares = (
        trade["notional"]
        / trade["price"]
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
        f"   Reference price: "
        f"${trade['price']:.2f}"
    )

    print(
        f"   Dollar order: "
        f"${trade['notional']:,.2f}"
    )

    print(
        f"   Approx shares: "
        f"{estimated_shares:.3f}"
    )

    print(
        f"   Client order ID: "
        f"{build_client_order_id(trade['ticker'])}"
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
        "             PAPER ORDER EXECUTOR v0.3"
    )

    print(
        "=============================================================="
    )

    print(
        f"Strategy: "
        f"{STRATEGY_VERSION}"
    )

    print(
        f"Execution enabled: "
        f"{EXECUTE_PAPER_ORDERS}"
    )

    print(
        "Broker mode: ALPACA PAPER ONLY"
    )

    print(
        "Trading mode: CASH ONLY / LONG ONLY"
    )

    print(
        "Margin: DISABLED BY BOT"
    )

    print(
        "Leverage: DISABLED BY BOT"
    )

    print(
        "Shorts: DISABLED"
    )

    print(
        "Options: DISABLED"
    )


    # ======================================================
    # ACCOUNT
    # ======================================================

    account = (
        trading_client.get_account()
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
        f"${float(account.equity):,.2f}"
    )

    print(
        f"Cash: "
        f"${float(account.cash):,.2f}"
    )

    print(
        f"Buying power reported by Alpaca: "
        f"${float(account.buying_power):,.2f}"
    )

    print(
        "Buying power is IGNORED by this bot."
    )

    print(
        f"Trading blocked: "
        f"{account.trading_blocked}"
    )


    if account.trading_blocked:

        print()
        print(
            "STOPPED: Alpaca reports "
            "trading is blocked."
        )

        return


    # ======================================================
    # MARKET CLOCK
    # ======================================================

    clock = (
        trading_client.get_clock()
    )


    print()
    print(
        f"Market open: "
        f"{clock.is_open}"
    )


    if not clock.is_open:

        print()
        print(
            "STOPPED: Market is closed."
        )

        print(
            "No orders submitted."
        )

        return


    # ======================================================
    # LOAD PREDICTIONS
    # ======================================================

    predictions = (
        get_latest_predictions()
    )


    if not predictions:

        print()
        print(
            "STOPPED: No strategy predictions "
            "found for today's market date."
        )

        return


    print()
    print(
        f"Predictions loaded: "
        f"{len(predictions)}"
    )


    # ======================================================
    # OFFICIAL SNAPSHOT SAFETY GATE
    # ======================================================

    snapshot_valid, snapshot_reason = (
        validate_snapshot(
            predictions,
            clock
        )
    )


    print()

    print(
        f"Snapshot valid: "
        f"{snapshot_valid}"
    )

    print(
        f"Reason: "
        f"{snapshot_reason}"
    )


    if not snapshot_valid:

        print()
        print(
            "=============================================================="
        )

        print(
            "EXECUTION BLOCKED BY SNAPSHOT SAFETY GATE"
        )

        print(
            "NO ORDERS WERE SUBMITTED"
        )

        print(
            "=============================================================="
        )

        return


    # ======================================================
    # CURRENT PAPER PORTFOLIO
    # ======================================================

    account_state = (
        get_account_state()
    )


    print()
    print(
        f"Open positions: "
        f"{account_state['open_positions_count']}"
    )

    print(
        f"Current exposure: "
        f"${account_state['current_exposure']:,.2f}"
    )


    # ======================================================
    # LONG-ONLY PORTFOLIO CHECK
    # ======================================================

    long_only_check = (
        validate_long_only_positions(
            account_state[
                "positions"
            ]
        )
    )


    if not long_only_check[
        "safe"
    ]:

        print()
        print(
            "=============================================================="
        )

        print(
            "EXECUTION BLOCKED"
        )

        print(
            "LONG-ONLY PORTFOLIO VALIDATION FAILED"
        )

        print(
            "=============================================================="
        )


        for violation in long_only_check[
            "violations"
        ]:

            print(
                f"  - {violation}"
            )


        print()
        print(
            "NO ORDERS WERE SUBMITTED"
        )

        return


    # ======================================================
    # HARD RISK ENGINE / TRADE PLAN
    # ======================================================

    trade_plan, rejected = (
        build_trade_plan(
            predictions,
            account_state
        )
    )


    print()
    print(
        "=============================================================="
    )

    print(
        "                APPROVED TRADE PLAN"
    )

    print(
        "=============================================================="
    )


    if not trade_plan:

        print()
        print(
            "No trades passed the hard risk engine."
        )

        return


    for number, trade in enumerate(
        trade_plan,
        start=1
    ):

        print_trade(
            number,
            trade
        )


    total_notional = sum(
        trade["notional"]
        for trade in trade_plan
    )


    print()
    print(
        "--------------------------------------------------------------"
    )

    print(
        f"Approved orders: "
        f"{len(trade_plan)}"
    )

    print(
        f"Total approved notional: "
        f"${total_notional:,.2f}"
    )


    # ======================================================
    # MASTER EXECUTION SWITCH
    # ======================================================

    if not EXECUTE_PAPER_ORDERS:

        print()
        print(
            "=============================================================="
        )

        print(
            "EXECUTION SWITCH IS OFF"
        )

        print(
            "NO ORDERS WERE SUBMITTED"
        )

        print(
            "=============================================================="
        )

        return


    # ======================================================
    # SUBMIT PAPER ORDERS
    # ======================================================

    print()
    print(
        "=============================================================="
    )

    print(
        "             SUBMITTING PAPER ORDERS"
    )

    print(
        "=============================================================="
    )


    submitted_count = 0

    failed_count = 0

    skipped_count = 0


    for trade in trade_plan:

        ticker = (
            trade[
                "ticker"
            ]
        )


        client_order_id = (
            build_client_order_id(
                ticker
            )
        )


        try:

            # ==================================================
            # FINAL CASH-ONLY / LONG-ONLY SAFETY CHECK
            #
            # Everything is re-fetched immediately before
            # each actual order.
            # ==================================================

            latest_account = (
                trading_client.get_account()
            )

            latest_positions = (
                trading_client.get_all_positions()
            )


            # --------------------------------------------------
            # LONG-ONLY VALIDATION
            # --------------------------------------------------

            long_only_check = (
                validate_long_only_positions(
                    latest_positions
                )
            )


            if not long_only_check[
                "safe"
            ]:

                print()
                print(
                    "EXECUTION BLOCKED:"
                )

                print(
                    "Long-only portfolio validation failed."
                )


                for violation in long_only_check[
                    "violations"
                ]:

                    print(
                        f"  - {violation}"
                    )


                print()
                print(
                    "NO FURTHER ORDERS WILL BE SUBMITTED."
                )

                return


            # --------------------------------------------------
            # EXISTING POSITION CHECK
            # --------------------------------------------------

            held_symbols = {
                position.symbol
                for position
                in latest_positions
            }


            if ticker in held_symbols:

                skipped_count += 1

                print()
                print(
                    f"SKIPPED {ticker}: "
                    f"position already exists."
                )

                continue


            # --------------------------------------------------
            # ACTUAL CASH CHECK
            #
            # IMPORTANT:
            #
            # account.buying_power is NEVER used here.
            # --------------------------------------------------

            latest_cash = float(
                latest_account.cash
            )

            latest_equity = float(
                latest_account.equity
            )


            minimum_cash_reserve = (
                latest_equity
                * MIN_CASH_RESERVE_PERCENT
            )


            spendable_cash = max(
                latest_cash
                - minimum_cash_reserve,
                0.0
            )


            proposed_notional = float(
                trade[
                    "notional"
                ]
            )


            print()
            print(
                f"FINAL CASH CHECK: "
                f"{ticker}"
            )

            print(
                f"  Actual cash: "
                f"${latest_cash:,.2f}"
            )

            print(
                f"  Required reserve: "
                f"${minimum_cash_reserve:,.2f}"
            )

            print(
                f"  Spendable cash: "
                f"${spendable_cash:,.2f}"
            )

            print(
                f"  Proposed order: "
                f"${proposed_notional:,.2f}"
            )


            # --------------------------------------------------
            # NEGATIVE CASH = STOP
            # --------------------------------------------------

            if latest_cash < 0:

                skipped_count += 1

                print(
                    f"  BLOCKED: "
                    f"cash balance is negative."
                )

                continue


            # --------------------------------------------------
            # ORDER CANNOT EXCEED ACTUAL CASH
            # --------------------------------------------------

            if (
                proposed_notional
                > latest_cash
            ):

                skipped_count += 1

                print(
                    f"  BLOCKED: "
                    f"order exceeds actual cash."
                )

                continue


            # --------------------------------------------------
            # ORDER CANNOT VIOLATE CASH RESERVE
            # --------------------------------------------------

            if (
                proposed_notional
                > spendable_cash
            ):

                skipped_count += 1

                print(
                    f"  BLOCKED: "
                    f"order would violate "
                    f"minimum cash reserve."
                )

                continue


            # ==================================================
            # PAPER MARKET ORDER
            #
            # BUY ONLY.
            # LONG STOCK ONLY.
            # CASH-SIZED ONLY.
            # ==================================================

            order_request = (
                MarketOrderRequest(

                    symbol=
                        ticker,

                    notional=
                        round(
                            proposed_notional,
                            2
                        ),

                    side=
                        OrderSide.BUY,

                    time_in_force=
                        TimeInForce.DAY,

                    client_order_id=
                        client_order_id
                )
            )


            order = (
                trading_client
                .submit_order(
                    order_data=
                        order_request
                )
            )


            submitted_count += 1


            print()
            print(
                f"SUBMITTED: "
                f"{ticker}"
            )

            print(
                f"  Notional: "
                f"${proposed_notional:,.2f}"
            )

            print(
                f"  Order ID: "
                f"{order.id}"
            )

            print(
                f"  Client ID: "
                f"{order.client_order_id}"
            )

            print(
                f"  Status: "
                f"{order.status}"
            )


        except Exception as error:

            failed_count += 1


            print()
            print(
                f"FAILED: "
                f"{ticker}"
            )

            print(
                f"  Error: "
                f"{error}"
            )


    # ======================================================
    # SUMMARY
    # ======================================================

    print()
    print(
        "=============================================================="
    )

    print(
        "             PAPER EXECUTION SUMMARY"
    )

    print(
        "=============================================================="
    )

    print(
        f"Submitted: "
        f"{submitted_count}"
    )

    print(
        f"Skipped: "
        f"{skipped_count}"
    )

    print(
        f"Failed: "
        f"{failed_count}"
    )

    print()

    print(
        "ALPACA PAPER ACCOUNT ONLY"
    )

    print(
        "CASH ONLY"
    )

    print(
        "LONG STOCKS ONLY"
    )

    print(
        "NO MARGIN / NO LEVERAGE"
    )

    print(
        "NO SHORTS / NO OPTIONS"
    )

    print(
        "=============================================================="
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    main()