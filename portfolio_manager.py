# ==========================================================
# AI TRADING BOT — PORTFOLIO MANAGER v0.1
#
# READ-ONLY / DRY-RUN
#
# This script:
#   - reads current Alpaca PAPER positions
#   - reads today's Combined Brain predictions
#   - evaluates existing positions
#   - decides HOLD / EXIT / REPLACE
#
# THIS SCRIPT CANNOT PLACE ORDERS.
# ==========================================================

from paper_trade_planner import (
    get_latest_predictions,
    get_account_state
)


# ==========================================================
# HARD PORTFOLIO RULES
# ==========================================================

# If conviction falls below this:
# exit the position.
EXIT_CONVICTION = 65.0

# Conviction at or above this:
# generally hold the position.
HOLD_CONVICTION = 75.0

# A replacement stock must at least meet our
# existing new-buy threshold.
REPLACEMENT_MIN_CONVICTION = 80.0

# Replacement must be meaningfully stronger than
# the stock we currently hold.
REPLACEMENT_ADVANTAGE = 10.0

# Hard downside protection.
# Example:
# -8.0 = exit after an 8% unrealized loss.
HARD_STOP_LOSS_PCT = -8.0

# HIGH risk can never remain in the portfolio.
BLOCKED_RISK_LEVELS = {
    "HIGH"
}


# ==========================================================
# FIND BEST REPLACEMENT
# ==========================================================

def find_best_replacement(
    predictions,
    held_symbols,
    current_conviction
):

    candidates = []

    for prediction in predictions:

        ticker = prediction[
            "ticker"
        ]

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


        # Already owned.
        if ticker in held_symbols:
            continue


        # Benchmark ETFs are not individual stock trades.
        if ticker in {
            "SPY",
            "QQQ"
        }:
            continue


        # High risk blocked.
        if risk in BLOCKED_RISK_LEVELS:
            continue


        # Must meet minimum new-position conviction.
        if conviction < REPLACEMENT_MIN_CONVICTION:
            continue


        # Must be meaningfully stronger than
        # the position it would replace.
        conviction_advantage = (
            conviction
            - current_conviction
        )

        if (
            conviction_advantage
            < REPLACEMENT_ADVANTAGE
        ):
            continue


        candidates.append(
            prediction
        )


    if not candidates:
        return None


    candidates.sort(
        key=lambda x:
            float(
                x[
                    "conviction"
                ]
            ),
        reverse=True
    )


    return candidates[0]


# ==========================================================
# EVALUATE EXISTING POSITION
# ==========================================================

def evaluate_position(
    position,
    prediction,
    predictions,
    held_symbols
):

    ticker = position.symbol

    market_value = float(
        position.market_value
    )

    current_price = float(
        position.current_price
    )

    unrealized_pl = float(
        position.unrealized_pl
    )

    unrealized_pl_pct = (
        float(
            position.unrealized_plpc
        )
        * 100
    )


    result = {

        "ticker":
            ticker,

        "action":
            "HOLD",

        "market_value":
            market_value,

        "current_price":
            current_price,

        "unrealized_pl":
            unrealized_pl,

        "unrealized_pl_pct":
            unrealized_pl_pct,

        "conviction":
            None,

        "risk":
            None,

        "replacement":
            None,

        "reasons":
            []
    }


    # ======================================================
    # NO CURRENT PREDICTION
    # ======================================================

    if prediction is None:

        result[
            "action"
        ] = "HOLD"

        result[
            "reasons"
        ].append(
            "No fresh prediction available. "
            "Do not force an exit without current data."
        )

        return result


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


    result[
        "conviction"
    ] = conviction

    result[
        "risk"
    ] = risk


    # ======================================================
    # RULE 1 — HARD STOP LOSS
    # ======================================================

    if (
        unrealized_pl_pct
        <= HARD_STOP_LOSS_PCT
    ):

        result[
            "action"
        ] = "EXIT"

        result[
            "reasons"
        ].append(
            f"Hard stop triggered: "
            f"{unrealized_pl_pct:.2f}% "
            f"<= {HARD_STOP_LOSS_PCT:.2f}%."
        )

        return result


    # ======================================================
    # RULE 2 — HIGH RISK
    # ======================================================

    if risk in BLOCKED_RISK_LEVELS:

        result[
            "action"
        ] = "EXIT"

        result[
            "reasons"
        ].append(
            f"Risk level {risk} "
            f"is blocked."
        )

        return result


    # ======================================================
    # RULE 3 — CONVICTION COLLAPSE
    # ======================================================

    if conviction < EXIT_CONVICTION:

        result[
            "action"
        ] = "EXIT"

        result[
            "reasons"
        ].append(
            f"Conviction {conviction:.1f} "
            f"is below exit threshold "
            f"{EXIT_CONVICTION:.1f}."
        )

        return result


    # ======================================================
    # RULE 4 — STRONG POSITION
    # ======================================================

    if conviction >= HOLD_CONVICTION:

        result[
            "action"
        ] = "HOLD"

        result[
            "reasons"
        ].append(
            f"Conviction {conviction:.1f} "
            f"is above hold threshold "
            f"{HOLD_CONVICTION:.1f}."
        )

        return result


    # ======================================================
    # RULE 5 — MIDDLE ZONE
    #
    # Position is not weak enough for automatic exit,
    # but not strong enough for an automatic hold.
    #
    # Look for a substantially better replacement.
    # ======================================================

    replacement = (
        find_best_replacement(
            predictions=
                predictions,

            held_symbols=
                held_symbols,

            current_conviction=
                conviction
        )
    )


    if replacement:

        result[
            "action"
        ] = "REPLACE"

        result[
            "replacement"
        ] = {
            "ticker":
                replacement[
                    "ticker"
                ],

            "conviction":
                float(
                    replacement[
                        "conviction"
                    ]
                ),

            "risk":
                replacement[
                    "risk"
                ]
        }

        result[
            "reasons"
        ].append(
            f"Current conviction is only "
            f"{conviction:.1f}."
        )

        result[
            "reasons"
        ].append(
            f"{replacement['ticker']} "
            f"has conviction "
            f"{float(replacement['conviction']):.1f}, "
            f"at least "
            f"{REPLACEMENT_ADVANTAGE:.1f} "
            f"points stronger."
        )

        return result


    # ======================================================
    # NO STRONG REPLACEMENT
    # ======================================================

    result[
        "action"
    ] = "HOLD"

    result[
        "reasons"
    ].append(
        f"Conviction {conviction:.1f} "
        f"is in the middle zone."
    )

    result[
        "reasons"
    ].append(
        "No sufficiently superior replacement exists."
    )

    return result


# ==========================================================
# DISPLAY POSITION DECISION
# ==========================================================

def print_decision(
    result
):

    print()
    print(
        "=============================================================="
    )

    print(
        f"{result['ticker']} — "
        f"{result['action']}"
    )

    print(
        "=============================================================="
    )

    print(
        f"Market value: "
        f"${result['market_value']:,.2f}"
    )

    print(
        f"Current price: "
        f"${result['current_price']:,.2f}"
    )

    print(
        f"Unrealized P/L: "
        f"${result['unrealized_pl']:,.2f} "
        f"({result['unrealized_pl_pct']:.2f}%)"
    )


    if result[
        "conviction"
    ] is not None:

        print(
            f"Current conviction: "
            f"{result['conviction']:.1f}"
        )

        print(
            f"Current risk: "
            f"{result['risk']}"
        )


    print()
    print(
        "Reasons:"
    )


    for reason in result[
        "reasons"
    ]:

        print(
            f"  - {reason}"
        )


    if result[
        "replacement"
    ]:

        replacement = result[
            "replacement"
        ]

        print()
        print(
            "Proposed replacement:"
        )

        print(
            f"  {replacement['ticker']}"
        )

        print(
            f"  Conviction: "
            f"{replacement['conviction']:.1f}"
        )

        print(
            f"  Risk: "
            f"{replacement['risk']}"
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
        "              PORTFOLIO MANAGER v0.1"
    )

    print(
        "=============================================================="
    )

    print(
        "DRY RUN / READ-ONLY"
    )

    print(
        "THIS SCRIPT CANNOT PLACE ORDERS"
    )


    # ======================================================
    # LOAD TODAY'S PREDICTIONS
    # ======================================================

    predictions = (
        get_latest_predictions()
    )


    if not predictions:

        print()
        print(
            "No predictions found for today's "
            "market date."
        )

        return


    prediction_map = {

        prediction[
            "ticker"
        ]:
            prediction

        for prediction in predictions
    }


    print()
    print(
        f"Predictions loaded: "
        f"{len(predictions)}"
    )


    # ======================================================
    # LOAD ACTUAL PAPER PORTFOLIO
    # ======================================================

    account_state = (
        get_account_state()
    )

    positions = account_state[
        "positions"
    ]

    held_symbols = {
        position.symbol
        for position in positions
    }


    print()
    print(
        "PAPER PORTFOLIO"
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
        f"Exposure: "
        f"${account_state['current_exposure']:,.2f}"
    )

    print(
        f"Positions: "
        f"{account_state['open_positions_count']}"
    )


    if not positions:

        print()
        print(
            "No existing paper positions "
            "to manage."
        )

        return


    # ======================================================
    # EVALUATE EACH POSITION
    # ======================================================

    decisions = []


    for position in positions:

        prediction = (
            prediction_map.get(
                position.symbol
            )
        )

        result = (
            evaluate_position(
                position=
                    position,

                prediction=
                    prediction,

                predictions=
                    predictions,

                held_symbols=
                    held_symbols
            )
        )

        decisions.append(
            result
        )

        print_decision(
            result
        )


    # ======================================================
    # SUMMARY
    # ======================================================

    print()
    print(
        "=============================================================="
    )

    print(
        "                 PORTFOLIO SUMMARY"
    )

    print(
        "=============================================================="
    )


    for decision in decisions:

        print(
            f"{decision['ticker']:<8} "
            f"{decision['action']}"
        )


    holds = sum(
        1
        for x in decisions
        if x[
            "action"
        ] == "HOLD"
    )

    exits = sum(
        1
        for x in decisions
        if x[
            "action"
        ] == "EXIT"
    )

    replacements = sum(
        1
        for x in decisions
        if x[
            "action"
        ] == "REPLACE"
    )


    print()
    print(
        f"HOLD:    {holds}"
    )

    print(
        f"EXIT:    {exits}"
    )

    print(
        f"REPLACE: {replacements}"
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