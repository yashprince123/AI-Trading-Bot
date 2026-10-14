import sqlite3


DATABASE = "trading_brain.db"


def create_database():

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT,

            ticker TEXT,

            price REAL,

            conviction REAL,

            market_score REAL,

            news_score REAL,

            return_5d REAL,

            return_20d REAL,

            relative_strength_20d REAL,

            volatility REAL,

            risk TEXT,

            trend TEXT,

            news_count INTEGER,

            price_1d REAL,
            return_1d REAL,

            price_5d REAL,
            return_after_5d REAL,

            price_20d REAL,
            return_after_20d REAL

        )
        """
    )

    connection.commit()
    connection.close()

    print(
        "Trading Brain database created successfully."
    )


if __name__ == "__main__":

    create_database()