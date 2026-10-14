import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


DATABASE = "trading_brain.db"

MARKET_TIMEZONE = ZoneInfo(
    "America/New_York"
)


# ==========================================================
# GET CURRENT MARKET DATE
# ==========================================================

def get_current_market_date():

    now_utc = datetime.now(
        timezone.utc
    )

    now_market = now_utc.astimezone(
        MARKET_TIMEZONE
    )

    return now_market.date()


# ==========================================================
# CHECK FOR EXISTING DAILY SNAPSHOT
# ==========================================================

def prediction_exists_today(
    ticker,
    strategy_version
):

    if not strategy_version:
        return False

    today_market = (
        get_current_market_date()
    )

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT timestamp

        FROM predictions

        WHERE ticker = ?
        AND strategy_version = ?
        """,
        (
            ticker,
            strategy_version
        )
    )

    rows = cursor.fetchall()

    connection.close()

    for row in rows:

        timestamp_text = row[0]

        try:

            prediction_time = (
                datetime.fromisoformat(
                    timestamp_text
                )
            )

            if prediction_time.tzinfo is None:

                prediction_time = (
                    prediction_time.replace(
                        tzinfo=timezone.utc
                    )
                )

            prediction_market_date = (
                prediction_time.astimezone(
                    MARKET_TIMEZONE
                ).date()
            )

            if (
                prediction_market_date
                == today_market
            ):

                return True

        except Exception:

            continue

    return False


# ==========================================================
# SAVE PREDICTION
# ==========================================================

def save_prediction(
    ticker,
    price,
    conviction,
    market_score,
    news_score,
    return_5d,
    return_20d,
    relative_strength_20d,
    volatility,
    risk,
    trend,
    news_count,
    strategy_version=None
):

    # ------------------------------------------------------
    # DO NOT CREATE A SECOND OFFICIAL DAILY SNAPSHOT
    # ------------------------------------------------------

    if prediction_exists_today(
        ticker,
        strategy_version
    ):

        return False


    # ------------------------------------------------------
    # SAVE NEW PREDICTION
    # ------------------------------------------------------

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO predictions (
            timestamp,
            ticker,
            price,
            conviction,
            market_score,
            news_score,
            return_5d,
            return_20d,
            relative_strength_20d,
            volatility,
            risk,
            trend,
            news_count,
            strategy_version
        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            datetime.now(
                timezone.utc
            ).isoformat(),

            ticker,
            price,
            conviction,
            market_score,
            news_score,
            return_5d,
            return_20d,
            relative_strength_20d,
            volatility,
            risk,
            trend,
            news_count,
            strategy_version
        )
    )

    connection.commit()
    connection.close()

    return True


# ==========================================================
# QUICK CHECK
# ==========================================================

if __name__ == "__main__":

    print(
        "Prediction logger ready."
    )

    print(
        f"Current market date: "
        f"{get_current_market_date()}"
    )

    print(
        "Daily duplicate protection enabled."
    )