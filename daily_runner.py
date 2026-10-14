import os
import sys
import subprocess
from pathlib import Path
from datetime import timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient


# ==========================================================
# SETTINGS
# ==========================================================

PROJECT_FOLDER = Path(
    __file__
).resolve().parent

GRADER_SCRIPT = (
    PROJECT_FOLDER
    / "prediction_grader.py"
)

BRAIN_SCRIPT = (
    PROJECT_FOLDER
    / "combined_brain.py"
)

SELL_EXECUTOR_SCRIPT = (
    PROJECT_FOLDER
    / "paper_sell_executor.py"
)

BUY_EXECUTOR_SCRIPT = (
    PROJECT_FOLDER
    / "paper_order_executor.py"
)

SNAPSHOT_MINUTES_BEFORE_CLOSE = 15

MOUNTAIN_TIMEZONE = ZoneInfo(
    "America/Denver"
)


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
# RUN SCRIPT
# ==========================================================

def run_script(script_path):

    print()
    print(
        "=============================================================="
    )

    print(
        f"RUNNING: {script_path.name}"
    )

    print(
        "=============================================================="
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script_path)
        ],
        cwd=PROJECT_FOLDER
    )

    if result.returncode != 0:

        print()
        print(
            f"ERROR: {script_path.name} failed."
        )

        return False

    return True


# ==========================================================
# FORMAT MOUNTAIN TIME
# ==========================================================

def format_mountain_time(value):

    mountain_time = (
        value.astimezone(
            MOUNTAIN_TIMEZONE
        )
    )

    return mountain_time.strftime(
        "%Y-%m-%d %I:%M:%S %p %Z"
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
        "                AI TRADING BRAIN DAILY RUNNER"
    )

    print(
        "=============================================================="
    )

    print(
        "Mode: RESEARCH + PAPER PORTFOLIO MANAGEMENT"
    )

    print(
        "Broker: ALPACA PAPER ONLY"
    )

    print(
        f"Official snapshot: "
        f"{SNAPSHOT_MINUTES_BEFORE_CLOSE} "
        f"minutes before market close"
    )


    # ======================================================
    # STEP 1 — GRADE OLD PREDICTIONS
    # ======================================================

    if not run_script(
        GRADER_SCRIPT
    ):

        print()
        print(
            "Stopping because grader failed."
        )

        return


    # ======================================================
    # STEP 2 — MARKET CLOCK
    # ======================================================

    print()
    print(
        "Checking US stock market status..."
    )

    clock = (
        trading_client.get_clock()
    )

    now = clock.timestamp

    next_open = clock.next_open

    next_close = clock.next_close


    print(
        f"Market open: "
        f"{clock.is_open}"
    )

    print(
        f"Current Mountain time: "
        f"{format_mountain_time(now)}"
    )

    print(
        f"Next market open: "
        f"{format_mountain_time(next_open)}"
    )

    print(
        f"Market close: "
        f"{format_mountain_time(next_close)}"
    )


    # ======================================================
    # STEP 3 — MARKET MUST BE OPEN
    # ======================================================

    if not clock.is_open:

        print()
        print(
            "Market is closed."
        )

        print(
            "Old predictions were graded, "
            "but no new snapshot or trades "
            "will be created."
        )

        return


    # ======================================================
    # STEP 4 — OFFICIAL SNAPSHOT TIME
    # ======================================================

    snapshot_time = (
        next_close
        - timedelta(
            minutes=
                SNAPSHOT_MINUTES_BEFORE_CLOSE
        )
    )


    print()
    print(
        f"Today's official snapshot time: "
        f"{format_mountain_time(snapshot_time)}"
    )


    # ======================================================
    # STEP 5 — TOO EARLY?
    # ======================================================

    if now < snapshot_time:

        time_remaining = (
            snapshot_time
            - now
        )

        total_seconds = int(
            time_remaining.total_seconds()
        )

        hours_remaining = (
            total_seconds // 3600
        )

        minutes_remaining = (
            (
                total_seconds % 3600
            )
            // 60
        )


        print()
        print(
            "Too early for today's "
            "official snapshot."
        )

        print(
            f"Time until snapshot: "
            f"{hours_remaining}h "
            f"{minutes_remaining}m"
        )

        print()
        print(
            "Grader completed."
        )

        print(
            "Combined Brain did NOT run."
        )

        print(
            "Sell Executor did NOT run."
        )

        print(
            "Buy Executor did NOT run."
        )

        return


    # ======================================================
    # STEP 6 — COMBINED BRAIN
    # ======================================================

    print()
    print(
        "Official snapshot time reached."
    )

    print(
        "Running Combined Brain..."
    )


    if not run_script(
        BRAIN_SCRIPT
    ):

        print()
        print(
            "Stopping because Combined Brain failed."
        )

        return


    # ======================================================
    # STEP 7 — SELL / POSITION MANAGEMENT
    # ======================================================

    print()
    print(
        "Combined Brain completed."
    )

    print(
        "Evaluating existing positions..."
    )


    if not run_script(
        SELL_EXECUTOR_SCRIPT
    ):

        print()
        print(
            "Stopping because Sell Executor failed."
        )

        return


    # ======================================================
    # STEP 8 — NEW BUY EXECUTOR
    # ======================================================

    print()
    print(
        "Position evaluation completed."
    )

    print(
        "Evaluating new paper buys..."
    )


    if not run_script(
        BUY_EXECUTOR_SCRIPT
    ):

        print()
        print(
            "Buy Executor failed."
        )

        return


    # ======================================================
    # FINISHED
    # ======================================================

    print()
    print(
        "=============================================================="
    )

    print(
        "DAILY PIPELINE COMPLETE"
    )

    print(
        "=============================================================="
    )

    print(
        "1. Old predictions graded."
    )

    print(
        "2. Fresh Combined Brain snapshot created."
    )

    print(
        "3. Existing positions evaluated."
    )

    print(
        "4. New paper positions evaluated."
    )

    print()

    print(
        "Buy execution is controlled by:"
    )

    print(
        "EXECUTE_PAPER_ORDERS"
    )

    print()

    print(
        "Sell execution is controlled by:"
    )

    print(
        "EXECUTE_PAPER_SELLS"
    )

    print(
        "=============================================================="
    )


if __name__ == "__main__":

    main()