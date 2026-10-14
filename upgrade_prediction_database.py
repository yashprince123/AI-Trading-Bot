import sqlite3


DATABASE = "trading_brain.db"


def upgrade_database():

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        PRAGMA table_info(predictions)
        """
    )

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "strategy_version" not in columns:

        cursor.execute(
            """
            ALTER TABLE predictions
            ADD COLUMN strategy_version TEXT
            """
        )

        print(
            "Added strategy_version column."
        )

    else:

        print(
            "strategy_version column already exists."
        )

    connection.commit()
    connection.close()

    print(
        "Prediction database upgrade complete."
    )


if __name__ == "__main__":

    upgrade_database()