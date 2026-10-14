# ==========================================================
# AI TRADING BOT — DIVERSIFICATION ENGINE v0.1
#
# PURPOSE:
#
# Prevent the portfolio from becoming concentrated even
# when many individual stocks have strong conviction.
#
# There is NO fixed number of holdings.
#
# Instead we limit:
#
# - individual sectors
# - highly related themes / clusters
#
# A trade can be REDUCED rather than simply rejected.
#
# Example:
#
# Desired NVDA position: $6,000
# Semiconductor capacity remaining: $2,000
#
# Result:
# Buy only $2,000.
#
# This module CANNOT place orders.
# ==========================================================


from risk_engine import MIN_POSITION_NOTIONAL


# ==========================================================
# HARD DIVERSIFICATION LIMITS
# ==========================================================

# No single broad sector may exceed 30%
# of total account equity.
MAX_SECTOR_PERCENT = 0.30


# Theme limits.
#
# Growth can remain the dominant style,
# but narrower correlated groups have tighter caps.
CLUSTER_LIMITS = {

    # Broad growth exposure may comprise
    # the majority of the portfolio.
    "GROWTH":
        0.60,

    # Semiconductor companies often move together.
    "SEMICONDUCTORS":
        0.20,

    # Enterprise/software companies can also
    # become a concentrated trade.
    "SOFTWARE":
        0.20,

    # Visa + Mastercard concentration.
    "PAYMENTS":
        0.15,

    # Energy concentration.
    "ENERGY":
        0.20
}


# ==========================================================
# STOCK CLASSIFICATION
#
# This covers the current Combined Brain universe.
#
# Unknown stocks are intentionally blocked until they
# receive a classification. This prevents a future stock
# from accidentally bypassing diversification rules.
# ==========================================================

STOCK_METADATA = {

    # ------------------------------------------------------
    # TECHNOLOGY
    # ------------------------------------------------------

    "AAPL": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "GROWTH"
        }
    },

    "MSFT": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "GROWTH",
            "SOFTWARE"
        }
    },

    "NVDA": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "GROWTH",
            "SEMICONDUCTORS"
        }
    },

    "AVGO": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "GROWTH",
            "SEMICONDUCTORS"
        }
    },

    "AMD": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "GROWTH",
            "SEMICONDUCTORS"
        }
    },

    "INTC": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "SEMICONDUCTORS"
        }
    },

    "CRM": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "GROWTH",
            "SOFTWARE"
        }
    },

    "ORCL": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "GROWTH",
            "SOFTWARE"
        }
    },

    "ADBE": {
        "sector": "TECHNOLOGY",
        "clusters": {
            "GROWTH",
            "SOFTWARE"
        }
    },


    # ------------------------------------------------------
    # COMMUNICATION SERVICES
    # ------------------------------------------------------

    "GOOGL": {
        "sector": "COMMUNICATION_SERVICES",
        "clusters": {
            "GROWTH"
        }
    },

    "META": {
        "sector": "COMMUNICATION_SERVICES",
        "clusters": {
            "GROWTH"
        }
    },

    "NFLX": {
        "sector": "COMMUNICATION_SERVICES",
        "clusters": {
            "GROWTH"
        }
    },


    # ------------------------------------------------------
    # CONSUMER DISCRETIONARY
    # ------------------------------------------------------

    "AMZN": {
        "sector": "CONSUMER_DISCRETIONARY",
        "clusters": {
            "GROWTH"
        }
    },

    "TSLA": {
        "sector": "CONSUMER_DISCRETIONARY",
        "clusters": {
            "GROWTH"
        }
    },


    # ------------------------------------------------------
    # FINANCIALS
    # ------------------------------------------------------

    "JPM": {
        "sector": "FINANCIALS",
        "clusters": set()
    },

    "V": {
        "sector": "FINANCIALS",
        "clusters": {
            "PAYMENTS"
        }
    },

    "MA": {
        "sector": "FINANCIALS",
        "clusters": {
            "PAYMENTS"
        }
    },


    # ------------------------------------------------------
    # CONSUMER STAPLES
    # ------------------------------------------------------

    "WMT": {
        "sector": "CONSUMER_STAPLES",
        "clusters": set()
    },

    "COST": {
        "sector": "CONSUMER_STAPLES",
        "clusters": set()
    },


    # ------------------------------------------------------
    # HEALTHCARE
    # ------------------------------------------------------

    "LLY": {
        "sector": "HEALTHCARE",
        "clusters": set()
    },

    "UNH": {
        "sector": "HEALTHCARE",
        "clusters": set()
    },


    # ------------------------------------------------------
    # ENERGY
    # ------------------------------------------------------

    "XOM": {
        "sector": "ENERGY",
        "clusters": {
            "ENERGY"
        }
    },

    "CVX": {
        "sector": "ENERGY",
        "clusters": {
            "ENERGY"
        }
    },


    # ------------------------------------------------------
    # BENCHMARKS
    #
    # These are currently not individual-stock trades.
    # ------------------------------------------------------

    "SPY": {
        "sector": "BENCHMARK",
        "clusters": set()
    },

    "QQQ": {
        "sector": "BENCHMARK",
        "clusters": set()
    }
}


# ==========================================================
# GET STOCK METADATA
# ==========================================================

def get_stock_metadata(
    ticker
):

    ticker = str(
        ticker
    ).upper()

    return STOCK_METADATA.get(
        ticker
    )


# ==========================================================
# EMPTY EXPOSURE STATE
# ==========================================================

def empty_exposure_state():

    return {

        "total":
            0.0,

        "sectors":
            {},

        "clusters":
            {}
    }


# ==========================================================
# ADD EXPOSURE
# ==========================================================

def add_exposure(
    exposure_state,
    ticker,
    notional
):

    ticker = str(
        ticker
    ).upper()

    notional = abs(
        float(
            notional
        )
    )

    metadata = (
        get_stock_metadata(
            ticker
        )
    )


    if metadata is None:

        return False


    sector = metadata[
        "sector"
    ]


    exposure_state[
        "total"
    ] += notional


    exposure_state[
        "sectors"
    ][sector] = (

        exposure_state[
            "sectors"
        ].get(
            sector,
            0.0
        )

        + notional
    )


    for cluster in metadata[
        "clusters"
    ]:

        exposure_state[
            "clusters"
        ][cluster] = (

            exposure_state[
                "clusters"
            ].get(
                cluster,
                0.0
            )

            + notional
        )


    return True


# ==========================================================
# BUILD EXPOSURE FROM ALPACA POSITIONS
# ==========================================================

def build_exposure_state(
    positions,
    planned_trades=None
):

    state = (
        empty_exposure_state()
    )


    # ======================================================
    # EXISTING POSITIONS
    # ======================================================

    for position in positions:

        ticker = (
            position.symbol
        )

        market_value = abs(
            float(
                position.market_value
            )
        )

        add_exposure(
            state,
            ticker,
            market_value
        )


    # ======================================================
    # ORDERS ALREADY PLANNED DURING THIS RUN
    # ======================================================

    if planned_trades:

        for trade in planned_trades:

            add_exposure(

                state,

                trade[
                    "ticker"
                ],

                trade[
                    "notional"
                ]
            )


    return state


# ==========================================================
# APPLY DIVERSIFICATION LIMITS
# ==========================================================

def apply_diversification_limits(
    ticker,
    proposed_notional,
    account_equity,
    exposure_state
):

    ticker = str(
        ticker
    ).upper()

    proposed_notional = float(
        proposed_notional
    )

    account_equity = float(
        account_equity
    )


    result = {

        "ticker":
            ticker,

        "allowed":
            True,

        "original_notional":
            proposed_notional,

        "adjusted_notional":
            proposed_notional,

        "sector":
            None,

        "clusters":
            [],

        "reasons":
            []
    }


    # ======================================================
    # VALIDATE ACCOUNT
    # ======================================================

    if account_equity <= 0:

        result[
            "allowed"
        ] = False

        result[
            "adjusted_notional"
        ] = 0.0

        result[
            "reasons"
        ].append(
            "Account equity must be positive."
        )

        return result


    # ======================================================
    # REQUIRE CLASSIFICATION
    # ======================================================

    metadata = (
        get_stock_metadata(
            ticker
        )
    )


    if metadata is None:

        result[
            "allowed"
        ] = False

        result[
            "adjusted_notional"
        ] = 0.0

        result[
            "reasons"
        ].append(

            f"{ticker} has no diversification "
            f"classification."
        )

        return result


    sector = metadata[
        "sector"
    ]

    clusters = metadata[
        "clusters"
    ]


    result[
        "sector"
    ] = sector

    result[
        "clusters"
    ] = sorted(
        clusters
    )


    # ======================================================
    # BENCHMARKS NOT TRADED
    # ======================================================

    if sector == "BENCHMARK":

        result[
            "allowed"
        ] = False

        result[
            "adjusted_notional"
        ] = 0.0

        result[
            "reasons"
        ].append(
            "Benchmark ETFs are not individual "
            "portfolio positions."
        )

        return result


    # ======================================================
    # START WITH ORIGINAL REQUEST
    # ======================================================

    adjusted_notional = (
        proposed_notional
    )


    # ======================================================
    # SECTOR CAPACITY
    # ======================================================

    sector_limit = (

        account_equity

        * MAX_SECTOR_PERCENT
    )


    current_sector_exposure = (

        exposure_state[
            "sectors"
        ].get(
            sector,
            0.0
        )
    )


    remaining_sector_capacity = max(

        sector_limit
        - current_sector_exposure,

        0.0
    )


    adjusted_notional = min(

        adjusted_notional,

        remaining_sector_capacity
    )


    if (
        adjusted_notional
        < proposed_notional
    ):

        result[
            "reasons"
        ].append(

            f"{sector} sector limit reduced "
            f"the proposed allocation."
        )


    # ======================================================
    # CLUSTER CAPACITIES
    # ======================================================

    for cluster in clusters:

        limit_percent = (
            CLUSTER_LIMITS.get(
                cluster
            )
        )


        if limit_percent is None:

            continue


        cluster_limit = (

            account_equity

            * limit_percent
        )


        current_cluster_exposure = (

            exposure_state[
                "clusters"
            ].get(
                cluster,
                0.0
            )
        )


        remaining_cluster_capacity = max(

            cluster_limit
            - current_cluster_exposure,

            0.0
        )


        before_cluster_check = (
            adjusted_notional
        )


        adjusted_notional = min(

            adjusted_notional,

            remaining_cluster_capacity
        )


        if (
            adjusted_notional
            < before_cluster_check
        ):

            result[
                "reasons"
            ].append(

                f"{cluster} concentration limit "
                f"reduced the allocation."
            )


    # ======================================================
    # MINIMUM POSITION
    # ======================================================

    if (
        adjusted_notional
        < MIN_POSITION_NOTIONAL
    ):

        result[
            "allowed"
        ] = False

        result[
            "adjusted_notional"
        ] = 0.0

        result[
            "reasons"
        ].append(

            f"Diversification-adjusted allocation "
            f"is below "
            f"${MIN_POSITION_NOTIONAL:,.2f}."
        )

        return result


    # ======================================================
    # SUCCESS
    # ======================================================

    result[
        "adjusted_notional"
    ] = round(
        adjusted_notional,
        2
    )


    if not result[
        "reasons"
    ]:

        result[
            "reasons"
        ].append(
            "Full proposed allocation fits "
            "diversification limits."
        )


    return result


# ==========================================================
# DISPLAY
# ==========================================================

def print_diversification_result(
    result
):

    print()
    print(
        "=============================================================="
    )

    print(
        f"DIVERSIFICATION CHECK: "
        f"{result['ticker']}"
    )

    print(
        "=============================================================="
    )


    print(
        f"Allowed: "
        f"{result['allowed']}"
    )

    print(
        f"Sector: "
        f"{result['sector']}"
    )

    print(
        f"Clusters: "
        f"{', '.join(result['clusters']) if result['clusters'] else 'NONE'}"
    )

    print(
        f"Original target: "
        f"${result['original_notional']:,.2f}"
    )

    print(
        f"Adjusted target: "
        f"${result['adjusted_notional']:,.2f}"
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


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print()
    print(
        "=============================================================="
    )

    print(
        "          DIVERSIFICATION ENGINE v0.1"
    )

    print(
        "=============================================================="
    )

    print(
        "NO ORDERS CAN BE PLACED"
    )


    # ======================================================
    # HYPOTHETICAL $100K PORTFOLIO
    #
    # Technology exposure:
    #
    # MSFT $10k
    # ORCL $8k
    # NVDA $9k
    #
    # Technology total = $27k
    #
    # Sector cap = $30k
    #
    # Therefore a new technology stock may only
    # receive another $3k maximum.
    # ======================================================

    equity = 100000


    exposure = (
        empty_exposure_state()
    )


    existing = [

        (
            "MSFT",
            10000
        ),

        (
            "ORCL",
            8000
        ),

        (
            "NVDA",
            9000
        ),

        (
            "GOOGL",
            5000
        )
    ]


    for ticker, notional in existing:

        add_exposure(
            exposure,
            ticker,
            notional
        )


    print()
    print(
        "CURRENT TEST EXPOSURE"
    )

    print(
        "--------------------------------------------------------------"
    )

    print(
        f"Total: "
        f"${exposure['total']:,.2f}"
    )

    print(
        f"Sectors: "
        f"{exposure['sectors']}"
    )

    print(
        f"Clusters: "
        f"{exposure['clusters']}"
    )


    # ======================================================
    # TEST 1
    #
    # AMD wants $6k.
    #
    # Technology only has $3k capacity.
    #
    # Expected result:
    # reduced to ~$3k.
    # ======================================================

    amd = apply_diversification_limits(

        ticker="AMD",

        proposed_notional=6000,

        account_equity=equity,

        exposure_state=exposure
    )


    print_diversification_result(
        amd
    )


    # ======================================================
    # TEST 2
    #
    # XOM is in a different sector.
    #
    # Expected:
    # full $6k allowed.
    # ======================================================

    xom = apply_diversification_limits(

        ticker="XOM",

        proposed_notional=6000,

        account_equity=equity,

        exposure_state=exposure
    )


    print_diversification_result(
        xom
    )


    # ======================================================
    # TEST 3
    #
    # Unknown ticker should be blocked until
    # we classify it.
    # ======================================================

    unknown = apply_diversification_limits(

        ticker="UNKNOWN",

        proposed_notional=5000,

        account_equity=equity,

        exposure_state=exposure
    )


    print_diversification_result(
        unknown
    )