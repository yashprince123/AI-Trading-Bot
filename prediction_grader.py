import os
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from alpaca.data.enums import DataFeed, Adjustment
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


# ==========================================================
# SETTINGS
# ==========================================================

DATABASE = "trading_brain.db"

STRATEGY_VERSION = "combined_v0.6"

MARKET_TIMEZONE = ZoneInfo(
    "America/New_York"
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
# MARKET DATA CLIENT
# ==========================================================

market_client = (
    StockHistoricalDataClient(
        API_KEY,
        SECRET_KEY
    )
)


# ==========================================================
# LOAD UNGRADED PREDICTIONS
# ==========================================================

def get_predictions_to_grade():

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
            strategy_version,

            price_1d,
            return_1d,

            price_5d,
            return_after_5d,

            price_20d,
            return_after_20d

        FROM predictions

        WHERE strategy_version = ?

        AND (
            return_1d IS NULL
            OR return_after_5d IS NULL
            OR return_after_20d IS NULL
        )

        ORDER BY timestamp ASC
        """,
        (
            STRATEGY_VERSION,
        )
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


# ==========================================================
# PARSE PREDICTION DATE
# ==========================================================

def get_prediction_market_date(
    timestamp_text
):

    prediction_time = (
        datetime.fromisoformat(
            timestamp_text
        )
    )

    # Older timestamps may theoretically
    # not contain timezone information.
    if prediction_time.tzinfo is None:

        prediction_time = (
            prediction_time.replace(
                tzinfo=timezone.utc
            )
        )

    market_time = (
        prediction_time.astimezone(
            MARKET_TIMEZONE
        )
    )

    return market_time.date()


# ==========================================================
# DOWNLOAD DAILY BARS
# ==========================================================

def download_bars(
    tickers,
    earliest_prediction
):

    print(
        "Downloading forward price data..."
    )

    request = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Day,

        start=datetime(
            earliest_prediction.year,
            earliest_prediction.month,
            earliest_prediction.day,
            tzinfo=MARKET_TIMEZONE
        ),

        end=datetime.now(
            timezone.utc
        ),

        feed=DataFeed.IEX,

        # Prediction prices are live/raw quotes.
        # We therefore compare against traded
        # daily closing prices.
        adjustment=Adjustment.RAW
    )

    return market_client.get_stock_bars(
        request
    )


# ==========================================================
# GET COMPLETED FUTURE SESSIONS
# ==========================================================

def get_future_sessions(
    ticker,
    prediction_date,
    bars
):

    try:

        ticker_bars = bars[
            ticker
        ]

    except Exception:

        return []

    now_et = datetime.now(
        MARKET_TIMEZONE
    )

    today_et = now_et.date()

    current_time = now_et.time()

    # Regular US equity close.
    # This is intentionally conservative:
    # during the trading day, today's
    # daily candle is not considered finished.
    market_close_hour = 16

    completed = []

    for bar in ticker_bars:

        bar_date = (
            bar.timestamp
            .astimezone(
                MARKET_TIMEZONE
            )
            .date()
        )

        # We only want sessions AFTER
        # the prediction's trading date.
        if bar_date <= prediction_date:
            continue

        # Never use an unfinished session.
        if bar_date == today_et:

            if current_time.hour < market_close_hour:
                continue

        completed.append(
            bar
        )

    completed.sort(
        key=lambda bar:
            bar.timestamp
    )

    return completed


# ==========================================================
# UPDATE ONE PREDICTION
# ==========================================================

def grade_prediction(
    prediction,
    bars
):

    prediction_id = (
        prediction["id"]
    )

    ticker = (
        prediction["ticker"]
    )

    entry_price = float(
        prediction["price"]
    )

    if entry_price <= 0:

        return {
            "updated": 0,
            "ticker": ticker,
            "available_days": 0
        }

    prediction_date = (
        get_prediction_market_date(
            prediction["timestamp"]
        )
    )

    future_sessions = (
        get_future_sessions(
            ticker,
            prediction_date,
            bars
        )
    )

    updates = {}

    # ======================================================
    # 1 TRADING DAY
    # ======================================================

    if (
        prediction["return_1d"]
        is None

        and

        len(future_sessions) >= 1
    ):

        price_1d = float(
            future_sessions[0].close
        )

        return_1d = (
            price_1d
            / entry_price
        ) - 1

        updates[
            "price_1d"
        ] = price_1d

        updates[
            "return_1d"
        ] = return_1d


    # ======================================================
    # 5 TRADING DAYS
    # ======================================================

    if (
        prediction["return_after_5d"]
        is None

        and

        len(future_sessions) >= 5
    ):

        price_5d = float(
            future_sessions[4].close
        )

        return_5d = (
            price_5d
            / entry_price
        ) - 1

        updates[
            "price_5d"
        ] = price_5d

        updates[
            "return_after_5d"
        ] = return_5d


    # ======================================================
    # 20 TRADING DAYS
    # ======================================================

    if (
        prediction["return_after_20d"]
        is None

        and

        len(future_sessions) >= 20
    ):

        price_20d = float(
            future_sessions[19].close
        )

        return_20d = (
            price_20d
            / entry_price
        ) - 1

        updates[
            "price_20d"
        ] = price_20d

        updates[
            "return_after_20d"
        ] = return_20d


    if not updates:

        return {
            "updated": 0,
            "ticker": ticker,
            "available_days":
                len(future_sessions)
        }


    # ======================================================
    # WRITE RESULTS TO SQLITE
    # ======================================================

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    set_statements = []

    values = []

    for column, value in (
        updates.items()
    ):

        set_statements.append(
            f"{column} = ?"
        )

        values.append(
            value
        )

    values.append(
        prediction_id
    )

    sql = (
        "UPDATE predictions SET "
        + ", ".join(
            set_statements
        )
        + " WHERE id = ?"
    )

    cursor.execute(
        sql,
        values
    )

    connection.commit()
    connection.close()

    return {
        "updated":
            len(updates) // 2,

        "ticker":
            ticker,

        "available_days":
            len(future_sessions),

        "updates":
            updates
    }


# ==========================================================
# MAIN GRADER
# ==========================================================

def run_grader():

    print()
    print(
        "=============================================================="
    )

    print(
        "                PREDICTION GRADER v0.1"
    )

    print(
        "=============================================================="
    )

    print(
        f"Strategy: {STRATEGY_VERSION}"
    )


    predictions = (
        get_predictions_to_grade()
    )


    if not predictions:

        print()
        print(
            "No ungraded predictions found."
        )

        return


    print()
    print(
        f"Predictions waiting for grading: "
        f"{len(predictions)}"
    )


    tickers = sorted(
        set(
            row["ticker"]
            for row in predictions
        )
    )


    prediction_dates = [
        get_prediction_market_date(
            row["timestamp"]
        )
        for row in predictions
    ]


    earliest_prediction = min(
        prediction_dates
    )


    bars = download_bars(
        tickers,
        earliest_prediction
    )


    # ======================================================
    # GRADE
    # ======================================================

    prediction_records_updated = 0

    horizon_results_added = 0

    waiting_for_1d = 0
    waiting_for_5d = 0
    waiting_for_20d = 0


    for prediction in predictions:

        result = grade_prediction(
            prediction,
            bars
        )

        if result[
            "updated"
        ] > 0:

            prediction_records_updated += 1

            horizon_results_added += (
                result["updated"]
            )


        available_days = (
            result[
                "available_days"
            ]
        )


        if (
            prediction[
                "return_1d"
            ] is None

            and

            available_days < 1
        ):

            waiting_for_1d += 1


        if (
            prediction[
                "return_after_5d"
            ] is None

            and

            available_days < 5
        ):

            waiting_for_5d += 1


        if (
            prediction[
                "return_after_20d"
            ] is None

            and

            available_days < 20
        ):

            waiting_for_20d += 1


    # ======================================================
    # SUMMARY
    # ======================================================

    print()
    print(
        "--------------------------------------------------------------"
    )

    print(
        "GRADING SUMMARY"
    )

    print(
        "--------------------------------------------------------------"
    )

    print(
        f"Prediction rows updated: "
        f"{prediction_records_updated}"
    )

    print(
        f"New horizon results added: "
        f"{horizon_results_added}"
    )

    print()

    print(
        f"Still waiting for 1D:  "
        f"{waiting_for_1d}"
    )

    print(
        f"Still waiting for 5D:  "
        f"{waiting_for_5d}"
    )

    print(
        f"Still waiting for 20D: "
        f"{waiting_for_20d}"
    )

    print()
    print(
        "=============================================================="
    )

    print(
        "GRADING COMPLETE"
    )

    print(
        "=============================================================="
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    run_grader()