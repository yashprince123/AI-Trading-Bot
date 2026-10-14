import os

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

from portfolio_manager import (
    evaluate_position
)

from paper_trade_planner import (
    get_latest_predictions,
    get_account_state
)


# ==========================================================
# SETTINGS
# ==========================================================

# False = print exit decisions only
# True  = actually close PAPER positions
#
# KEEP FALSE FOR NOW.
EXECUTE_PAPER_SELLS = False


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
# ALPACA PAPER CLIENT
# ==========================================================

trading_client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True
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
        "              PAPER SELL EXECUTOR v0.1"
    )

    print(
        "=============================================================="
    )

    print(
        f"Execution enabled: "
        f"{EXECUTE_PAPER_SELLS}"
    )

    print(
        "Broker mode: ALPACA PAPER ONLY"
    )


    # ======================================================
    # MARKET CHECK
    # ======================================================

    clock = trading_client.get_clock()

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
            "No sell orders submitted."
        )

        return


    # ======================================================
    # LOAD TODAY'S PREDICTIONS
    # ======================================================

    predictions = (
        get_latest_predictions()
    )


    if not predictions:

        print()
        print(
            "STOPPED: No predictions found "
            "for today's market date."
        )

        return


    prediction_map = {

        prediction["ticker"]:
            prediction

        for prediction in predictions
    }


    # ======================================================
    # LOAD CURRENT PAPER POSITIONS
    # ======================================================

    account_state = (
        get_account_state()
    )

    positions = (
        account_state["positions"]
    )

    held_symbols = {
        position.symbol
        for position in positions
    }


    print()
    print(
        "CURRENT PAPER PORTFOLIO"
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
        f"Positions: "
        f"{account_state['open_positions_count']}"
    )


    if not positions:

        print()
        print(
            "No open positions to manage."
        )

        return


    # ======================================================
    # EVALUATE POSITIONS
    # ======================================================

    decisions = []


    for position in positions:

        prediction = (
            prediction_map.get(
                position.symbol
            )
        )

        result = evaluate_position(
            position=
                position,

            prediction=
                prediction,

            predictions=
                predictions,

            held_symbols=
                held_symbols
        )

        decisions.append(
            result
        )


    # ======================================================
    # DISPLAY DECISIONS
    # ======================================================

    print()
    print(
        "=============================================================="
    )

    print(
        "                 SELL DECISIONS"
    )

    print(
        "=============================================================="
    )


    for result in decisions:

        print()
        print(
            f"{result['ticker']}"
        )

        print(
            f"  Action: "
            f"{result['action']}"
        )

        print(
            f"  Market value: "
            f"${result['market_value']:,.2f}"
        )

        print(
            f"  Unrealized P/L: "
            f"{result['unrealized_pl_pct']:.2f}%"
        )


        if (
            result["conviction"]
            is not None
        ):

            print(
                f"  Conviction: "
                f"{result['conviction']:.1f}"
            )

            print(
                f"  Risk: "
                f"{result['risk']}"
            )


        for reason in result[
            "reasons"
        ]:

            print(
                f"  Reason: "
                f"{reason}"
            )


        if (
            result["action"]
            == "REPLACE"
        ):

            replacement = (
                result[
                    "replacement"
                ]
            )

            print(
                f"  Replacement candidate: "
                f"{replacement['ticker']} "
                f"({replacement['conviction']:.1f})"
            )


    # ======================================================
    # EXECUTION SAFETY SWITCH
    # ======================================================

    if not EXECUTE_PAPER_SELLS:

        print()
        print(
            "=============================================================="
        )

        print(
            "SELL EXECUTION SWITCH IS OFF"
        )

        print(
            "NO POSITIONS WERE CLOSED"
        )

        print(
            "=============================================================="
        )

        return


    # ======================================================
    # EXECUTE EXITS
    # ======================================================

    print()
    print(
        "=============================================================="
    )

    print(
        "            SUBMITTING PAPER EXITS"
    )

    print(
        "=============================================================="
    )


    closed_count = 0
    skipped_count = 0
    failed_count = 0


    for result in decisions:

        ticker = (
            result["ticker"]
        )

        action = (
            result["action"]
        )


        # ----------------------------------------------
        # HOLD = DO NOTHING
        # ----------------------------------------------

        if action == "HOLD":

            skipped_count += 1

            print()
            print(
                f"HOLD: {ticker}"
            )

            continue


        # ----------------------------------------------
        # REPLACE
        #
        # We are NOT automating replacements yet.
        # ----------------------------------------------

        if action == "REPLACE":

            skipped_count += 1

            print()
            print(
                f"REPLACE NOT EXECUTED: "
                f"{ticker}"
            )

            print(
                "Replacement automation "
                "is intentionally disabled."
            )

            continue


        # ----------------------------------------------
        # EXIT
        # ----------------------------------------------

        if action == "EXIT":

            try:

                # Final check that the position
                # still exists immediately before
                # submitting the close request.

                trading_client.get_open_position(
                    ticker
                )


                order = (
                    trading_client
                    .close_position(
                        ticker
                    )
                )


                closed_count += 1


                print()
                print(
                    f"EXIT SUBMITTED: "
                    f"{ticker}"
                )

                print(
                    f"  Order ID: "
                    f"{order.id}"
                )

                print(
                    f"  Status: "
                    f"{order.status}"
                )


            except Exception as error:

                failed_count += 1

                print()
                print(
                    f"FAILED TO EXIT: "
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
        "             PAPER SELL SUMMARY"
    )

    print(
        "=============================================================="
    )

    print(
        f"Exit orders submitted: "
        f"{closed_count}"
    )

    print(
        f"Holds/replacements skipped: "
        f"{skipped_count}"
    )

    print(
        f"Failures: "
        f"{failed_count}"
    )

    print()

    print(
        "ALPACA PAPER ACCOUNT ONLY"
    )

    print(
        "=============================================================="
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    main()