import sqlite3
import hashlib
from datetime import datetime, timezone


DATABASE = "trading_brain.db"

# ==========================================================
# NEWS ANALYSIS IDENTITY
# ==========================================================

CACHE_MODEL = "qwen3:14b"
ANALYSIS_VERSION = 1


# ==========================================================
# CREATE / UPGRADE CACHE TABLE
# ==========================================================

def create_news_cache():

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_analysis_cache (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cache_key TEXT UNIQUE NOT NULL,

            ticker TEXT NOT NULL,

            headline TEXT NOT NULL,

            sentiment TEXT,

            sentiment_score REAL,

            importance INTEGER,

            relevance INTEGER,

            time_horizon TEXT,

            event_type TEXT,

            reason TEXT,

            model TEXT,

            analysis_version INTEGER,

            created_at TEXT
        )
        """
    )

    # ------------------------------------------------------
    # Upgrade older database if analysis_version
    # column does not exist yet
    # ------------------------------------------------------

    cursor.execute(
        """
        PRAGMA table_info(news_analysis_cache)
        """
    )

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "analysis_version" not in columns:

        cursor.execute(
            """
            ALTER TABLE news_analysis_cache
            ADD COLUMN analysis_version INTEGER
            """
        )

    connection.commit()
    connection.close()


# ==========================================================
# BUILD UNIQUE CACHE KEY
# ==========================================================

def build_cache_key(
    ticker,
    headline,
    summary,
    model=CACHE_MODEL,
    analysis_version=ANALYSIS_VERSION
):

    raw_text = (
        ticker.strip().upper()
        + "|"
        + headline.strip()
        + "|"
        + summary.strip()
        + "|"
        + model.strip()
        + "|"
        + str(analysis_version)
    )

    return hashlib.sha256(
        raw_text.encode(
            "utf-8"
        )
    ).hexdigest()


# ==========================================================
# CHECK CACHE
# ==========================================================

def get_cached_analysis(
    ticker,
    headline,
    summary,
    model=CACHE_MODEL,
    analysis_version=ANALYSIS_VERSION
):

    cache_key = build_cache_key(
        ticker,
        headline,
        summary,
        model,
        analysis_version
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
            sentiment,
            sentiment_score,
            importance,
            relevance,
            time_horizon,
            event_type,
            reason,
            model,
            analysis_version

        FROM news_analysis_cache

        WHERE cache_key = ?
        """,
        (
            cache_key,
        )
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return {

        "sentiment":
            row["sentiment"],

        "sentiment_score":
            row["sentiment_score"],

        "importance":
            row["importance"],

        "relevance":
            row["relevance"],

        "time_horizon":
            row["time_horizon"],

        "event_type":
            row["event_type"],

        "reason":
            row["reason"]
    }


# ==========================================================
# SAVE AI ANALYSIS
# ==========================================================

def save_cached_analysis(
    ticker,
    headline,
    summary,
    analysis,
    model=CACHE_MODEL,
    analysis_version=ANALYSIS_VERSION
):

    cache_key = build_cache_key(
        ticker,
        headline,
        summary,
        model,
        analysis_version
    )

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO news_analysis_cache (

            cache_key,

            ticker,
            headline,

            sentiment,
            sentiment_score,

            importance,
            relevance,

            time_horizon,
            event_type,

            reason,

            model,
            analysis_version,

            created_at
        )

        VALUES (
            ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?,
            ?, ?,
            ?
        )
        """,
        (
            cache_key,

            ticker,
            headline,

            analysis.get(
                "sentiment",
                "neutral"
            ),

            float(
                analysis.get(
                    "sentiment_score",
                    0
                )
            ),

            int(
                analysis.get(
                    "importance",
                    1
                )
            ),

            int(
                analysis.get(
                    "relevance",
                    1
                )
            ),

            analysis.get(
                "time_horizon",
                "days"
            ),

            analysis.get(
                "event_type",
                "other"
            ),

            analysis.get(
                "reason",
                ""
            ),

            model,

            analysis_version,

            datetime.now(
                timezone.utc
            ).isoformat()
        )
    )

    connection.commit()
    connection.close()


# ==========================================================
# RUN DIRECTLY
# ==========================================================

if __name__ == "__main__":

    create_news_cache()

    print(
        "Version-aware news cache ready."
    )

    print(
        f"Model: {CACHE_MODEL}"
    )

    print(
        f"Analysis version: {ANALYSIS_VERSION}"
    )