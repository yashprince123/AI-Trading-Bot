# ==========================================================
# AI TRADING BOT — HARD RISK ENGINE v0.3
# DYNAMIC PORTFOLIO WEIGHTING
#
# CASH ONLY
# LONG STOCKS ONLY
# NO MARGIN
# NO LEVERAGE
# NO SHORTS
# NO OPTIONS
#
# IMPORTANT:
#
# There is NO fixed maximum number of stocks.
#
# The portfolio is controlled by:
#
# - conviction
# - stock risk
# - market regime
# - maximum single-stock exposure
# - maximum total portfolio exposure
# - minimum cash reserve
#
# Future versions will additionally apply:
#
# - sector concentration
# - correlation concentration
# - growth / defensive classification
#
# This module CANNOT place trades.
# ==========================================================


# ==========================================================
# TRADING MODE
# ==========================================================

CASH_ONLY_MODE = True

ALLOW_MARGIN = False
ALLOW_LEVERAGE = False
ALLOW_SHORTS = False
ALLOW_OPTIONS = False


# ==========================================================
# PORTFOLIO LIMITS
# ==========================================================

# The bot can invest up to 90% of account equity.
MAX_TOTAL_EXPOSURE_PERCENT = 0.90

# Always preserve at least 10% cash.
MIN_CASH_RESERVE_PERCENT = 0.10

# One company may never represent more than
# 10% of account equity.
MAX_POSITION_PERCENT = 0.10

# Don't bother opening positions smaller than $100.
MIN_POSITION_NOTIONAL = 100.0


# ==========================================================
# CONVICTION SETTINGS
# ==========================================================

# Below this point, a stock receives no allocation.
MIN_CONVICTION = 70.0

# 100 conviction corresponds to the maximum
# allowed 10% position.
MAX_CONVICTION = 100.0


# ==========================================================
# RISK SETTINGS
# ==========================================================

BLOCKED_RISK_LEVELS = {
    "HIGH"
}


RISK_MULTIPLIERS = {

    "LOW":
        1.00,

    "MED":
        0.75,

    "MEDIUM":
        0.75,

    "HIGH":
        0.00
}


# ==========================================================
# CONVICTION → TARGET WEIGHT
#
# Uses a convex curve rather than fixed buckets.
#
# This means:
#
# mediocre signals receive tiny allocations,
# while exceptional signals receive increasingly
# larger allocations.
#
# Approximate LOW-risk allocations:
#
# Conviction 70 -> 0.00%
# Conviction 73 -> 0.10%
# Conviction 75 -> 0.28%
# Conviction 80 -> 1.11%
# Conviction 85 -> 2.50%
# Conviction 90 -> 4.44%
# Conviction 95 -> 6.94%
# Conviction 100 -> 10.00%
#
# On a $100k account:
#
# 73  -> ~$100
# 80  -> ~$1,111
# 85  -> ~$2,500
# 90  -> ~$4,444
# 95  -> ~$6,944
# 100 -> ~$10,000
#
# ==========================================================

def get_base_allocation_percent(
    conviction
):

    conviction = float(
        conviction
    )


    if conviction <= MIN_CONVICTION:

        return 0.0


    conviction = min(
        conviction,
        MAX_CONVICTION
    )


    normalized = (

        (
            conviction
            - MIN_CONVICTION
        )

        /

        (
            MAX_CONVICTION
            - MIN_CONVICTION
        )
    )


    # Convex curve.
    #
    # High-conviction signals receive
    # proportionally more capital.
    curved_score = (
        normalized ** 2
    )


    allocation = (

        MAX_POSITION_PERCENT

        * curved_score
    )


    return min(
        allocation,
        MAX_POSITION_PERCENT
    )


# ==========================================================
# LONG-ONLY PORTFOLIO VALIDATION
# ==========================================================

def validate_long_only_positions(
    positions
):

    violations = []


    for position in positions:

        ticker = str(
            position.symbol
        ).upper()


        qty = float(
            position.qty
        )


        if qty < 0:

            violations.append(

                f"{ticker} has negative quantity "
                f"{qty}. Short positions are forbidden."
            )


    return {

        "safe":
            len(violations) == 0,

        "violations":
            violations
    }


# ==========================================================
# EVALUATE NEW POSITION
# ==========================================================

def evaluate_new_position(
    ticker,
    conviction,
    risk,
    account_equity,
    cash,
    current_exposure,
    open_positions_count=None,
    market_regime_multiplier=1.0
):

    """
    Evaluate a NEW long-stock position.

    NOTE:
    open_positions_count is accepted only so existing
    bot code remains compatible.

    It is intentionally NOT used.

    There is no fixed position-count limit anymore.

    market_regime_multiplier:

        1.00 = strong / normal
        0.75 = mildly cautious
        0.50 = defensive
        0.25 = very defensive

    Until our Market Regime Brain exists,
    existing callers automatically use 1.00.
    """


    # ======================================================
    # NORMALIZE INPUTS
    # ======================================================

    ticker = str(
        ticker
    ).upper()


    conviction = float(
        conviction
    )


    risk = str(
        risk
    ).upper()


    account_equity = float(
        account_equity
    )


    cash = float(
        cash
    )


    current_exposure = float(
        current_exposure
    )


    market_regime_multiplier = float(
        market_regime_multiplier
    )


    # ======================================================
    # RESULT CONTAINER
    # ======================================================

    result = {

        "ticker":
            ticker,

        "allowed":
            True,

        "target_notional":
            0.0,

        "conviction":
            conviction,

        "risk":
            risk,

        "base_allocation_percent":
            0.0,

        "risk_multiplier":
            0.0,

        "market_regime_multiplier":
            market_regime_multiplier,

        "final_allocation_percent":
            0.0,

        "reasons":
            [],

        "limits":
            {},

        "safety": {

            "cash_only":
                CASH_ONLY_MODE,

            "margin_allowed":
                ALLOW_MARGIN,

            "leverage_allowed":
                ALLOW_LEVERAGE,

            "shorts_allowed":
                ALLOW_SHORTS,

            "options_allowed":
                ALLOW_OPTIONS
        }
    }


    # ======================================================
    # BASIC ACCOUNT VALIDATION
    # ======================================================

    if account_equity <= 0:

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(
            "Account equity must be greater than zero."
        )


    if cash < 0:

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(
            "Cash balance is negative."
        )


    if current_exposure < 0:

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(
            "Current exposure cannot be negative "
            "in long-only mode."
        )


    # ======================================================
    # MARKET REGIME VALIDATION
    # ======================================================

    if (
        market_regime_multiplier < 0
        or
        market_regime_multiplier > 1
    ):

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(
            "Market regime multiplier must "
            "be between 0 and 1."
        )


    # ======================================================
    # CONVICTION CHECK
    # ======================================================

    if conviction <= MIN_CONVICTION:

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(

            f"Conviction {conviction:.1f} "
            f"is not above minimum "
            f"{MIN_CONVICTION:.1f}."
        )


    # ======================================================
    # RISK CHECK
    # ======================================================

    if risk in BLOCKED_RISK_LEVELS:

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(

            f"Risk level {risk} "
            f"is blocked."
        )


    # ======================================================
    # BASE CONVICTION ALLOCATION
    # ======================================================

    base_allocation_percent = (
        get_base_allocation_percent(
            conviction
        )
    )


    # ======================================================
    # STOCK RISK MULTIPLIER
    # ======================================================

    risk_multiplier = (
        RISK_MULTIPLIERS.get(
            risk,
            0.50
        )
    )


    # ======================================================
    # FINAL TARGET WEIGHT
    #
    # conviction
    #     ×
    # stock risk
    #     ×
    # market environment
    # ======================================================

    final_allocation_percent = (

        base_allocation_percent

        * risk_multiplier

        * market_regime_multiplier
    )


    final_allocation_percent = min(

        final_allocation_percent,

        MAX_POSITION_PERCENT
    )


    result[
        "base_allocation_percent"
    ] = base_allocation_percent


    result[
        "risk_multiplier"
    ] = risk_multiplier


    result[
        "final_allocation_percent"
    ] = final_allocation_percent


    # ======================================================
    # DYNAMIC POSITION TARGET
    # ======================================================

    dynamic_target_notional = (

        account_equity

        * final_allocation_percent
    )


    # ======================================================
    # TOTAL PORTFOLIO LIMIT
    # ======================================================

    max_total_exposure = (

        account_equity

        * MAX_TOTAL_EXPOSURE_PERCENT
    )


    remaining_exposure_capacity = (

        max_total_exposure

        - current_exposure
    )


    remaining_exposure_capacity = max(

        remaining_exposure_capacity,

        0.0
    )


    # ======================================================
    # CASH RESERVE
    # ======================================================

    minimum_cash_reserve = (

        account_equity

        * MIN_CASH_RESERVE_PERCENT
    )


    spendable_cash = (

        cash

        - minimum_cash_reserve
    )


    spendable_cash = max(

        spendable_cash,

        0.0
    )


    # ======================================================
    # SINGLE-STOCK HARD CAP
    # ======================================================

    max_single_position = (

        account_equity

        * MAX_POSITION_PERCENT
    )


    # ======================================================
    # FINAL NEW-POSITION SIZE
    #
    # The most restrictive constraint wins.
    #
    # Buying power is NEVER considered.
    # ======================================================

    target_notional = min(

        dynamic_target_notional,

        max_single_position,

        remaining_exposure_capacity,

        spendable_cash,

        cash
    )


    target_notional = max(

        target_notional,

        0.0
    )


    # ======================================================
    # TOTAL EXPOSURE CHECK
    # ======================================================

    if remaining_exposure_capacity <= 0:

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(
            "Maximum 90% portfolio exposure "
            "has already been reached."
        )


    # ======================================================
    # CASH RESERVE CHECK
    # ======================================================

    if spendable_cash <= 0:

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(
            "Trade would violate the "
            "10% opportunity cash reserve."
        )


    # ======================================================
    # MINIMUM USEFUL POSITION
    # ======================================================

    if target_notional < MIN_POSITION_NOTIONAL:

        result[
            "allowed"
        ] = False

        result[
            "reasons"
        ].append(

            f"Calculated position "
            f"${target_notional:,.2f} "
            f"is below the minimum useful position "
            f"of ${MIN_POSITION_NOTIONAL:,.2f}."
        )


    # ======================================================
    # FINAL DECISION
    # ======================================================

    if result[
        "allowed"
    ]:

        result[
            "target_notional"
        ] = round(
            target_notional,
            2
        )


        result[
            "reasons"
        ].append(
            "Trade passes dynamic "
            "cash-only portfolio rules."
        )


    else:

        result[
            "target_notional"
        ] = 0.0


    # ======================================================
    # LIMIT DETAILS
    # ======================================================

    result[
        "limits"
    ] = {

        "account_equity":
            round(
                account_equity,
                2
            ),

        "actual_cash":
            round(
                cash,
                2
            ),

        "dynamic_target_notional":
            round(
                dynamic_target_notional,
                2
            ),

        "max_single_position":
            round(
                max_single_position,
                2
            ),

        "max_total_exposure":
            round(
                max_total_exposure,
                2
            ),

        "remaining_exposure_capacity":
            round(
                remaining_exposure_capacity,
                2
            ),

        "minimum_cash_reserve":
            round(
                minimum_cash_reserve,
                2
            ),

        "spendable_cash":
            round(
                spendable_cash,
                2
            )
    }


    return result


# ==========================================================
# DISPLAY RESULT
# ==========================================================

def print_risk_result(
    result
):

    print()
    print(
        "=============================================================="
    )

    print(
        f"RISK CHECK: "
        f"{result['ticker']}"
    )

    print(
        "=============================================================="
    )


    print(
        f"Conviction: "
        f"{result['conviction']:.1f}"
    )

    print(
        f"Risk: "
        f"{result['risk']}"
    )

    print(
        f"Allowed: "
        f"{result['allowed']}"
    )


    print()
    print(
        "DYNAMIC POSITION SIZING"
    )

    print(
        "--------------------------------------------------------------"
    )


    print(
        f"Base allocation: "
        f"{result['base_allocation_percent'] * 100:.2f}%"
    )


    print(
        f"Risk multiplier: "
        f"{result['risk_multiplier']:.2f}x"
    )


    print(
        f"Market multiplier: "
        f"{result['market_regime_multiplier']:.2f}x"
    )


    print(
        f"Final target allocation: "
        f"{result['final_allocation_percent'] * 100:.2f}%"
    )


    print(
        f"Target notional: "
        f"${result['target_notional']:,.2f}"
    )


    print()
    print(
        "TRADING MODE"
    )

    print(
        "--------------------------------------------------------------"
    )

    print(
        "Cash only: YES"
    )

    print(
        "Margin: NO"
    )

    print(
        "Leverage: NO"
    )

    print(
        "Shorts: NO"
    )

    print(
        "Options: NO"
    )

    print(
        "Fixed stock-count limit: NONE"
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


    print()
    print(
        "Hard limits:"
    )


    for name, value in result[
        "limits"
    ].items():

        print(
            f"  {name}: "
            f"${value:,.2f}"
        )


    print(
        "=============================================================="
    )


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print()
    print(
        "=============================================================="
    )

    print(
        "             HARD RISK ENGINE v0.3"
    )

    print(
        "=============================================================="
    )

    print(
        "DYNAMIC PORTFOLIO WEIGHTING"
    )

    print(
        "NO FIXED NUMBER OF STOCKS"
    )

    print(
        "NO ORDERS CAN BE PLACED"
    )


    equity = 100000

    cash = 70000

    exposure = 30000


    tests = [

        (
            "TEST73",
            73,
            "LOW"
        ),

        (
            "TEST80",
            80,
            "LOW"
        ),

        (
            "TEST85",
            85,
            "LOW"
        ),

        (
            "TEST90",
            90,
            "LOW"
        ),

        (
            "TEST95",
            95,
            "LOW"
        ),

        (
            "MED90",
            90,
            "MED"
        ),

        (
            "HIGH95",
            95,
            "HIGH"
        )
    ]


    for (
        ticker,
        conviction,
        risk
    ) in tests:

        result = (
            evaluate_new_position(

                ticker=
                    ticker,

                conviction=
                    conviction,

                risk=
                    risk,

                account_equity=
                    equity,

                cash=
                    cash,

                current_exposure=
                    exposure,

                open_positions_count=
                    999
            )
        )


        print_risk_result(
            result
        )