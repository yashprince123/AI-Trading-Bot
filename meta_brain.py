# ==========================================================
# AI TRADING BOT — META BRAIN / CIO v0.2
#
# SUPERVISORY AI WITH DETERMINISTIC VALIDATION
#
# Qwen may:
# - interpret the portfolio
# - identify concerns
# - suggest research hypotheses
# - suggest advisory portfolio actions
#
# Qwen may NOT:
# - place orders
# - modify code
# - change production parameters
# - override hard risk rules
# - determine whether evidence is statistically sufficient
#
# Python remains the source of truth for:
# - arithmetic
# - portfolio percentages
# - risk eligibility
# - sample sizes
# - evidence gates
#
# NO ORDERS.
# NO FILE MODIFICATION.
# NO DATABASE WRITES.
# ==========================================================


import json
import sqlite3
from statistics import mean

import requests

from paper_trade_planner import (
    get_latest_predictions,
    get_account_state
)

from diversification_engine import (
    build_exposure_state,
    MAX_SECTOR_PERCENT,
    CLUSTER_LIMITS
)

from risk_engine import (
    MIN_CONVICTION,
    BLOCKED_RISK_LEVELS
)


# ==========================================================
# SETTINGS
# ==========================================================

DATABASE = "trading_brain.db"

STRATEGY_VERSION = "combined_v0.6"

OLLAMA_URL = (
    "http://localhost:11434/api/chat"
)

MODEL = "qwen3:14b"

HISTORICAL_LIMIT = 1000


# ==========================================================
# ALGORITHM EVIDENCE GATES
#
# Qwen CANNOT override these.
#
# Until all three requirements are satisfied,
# algorithm-change recommendations remain only
# research hypotheses.
# ==========================================================

MIN_TOTAL_ROWS_FOR_ALGO_CHANGE = 300

MIN_GRADED_5D_FOR_ALGO_CHANGE = 200

MIN_GRADED_20D_FOR_ALGO_CHANGE = 100


# ==========================================================
# HELPER
# ==========================================================

def safe_float(value):

    if value is None:
        return None

    try:
        return float(value)

    except Exception:
        return None


# ==========================================================
# AVERAGE
# ==========================================================

def average_or_none(values):

    clean = [

        float(value)

        for value in values

        if value is not None
    ]

    if not clean:
        return None

    return mean(clean)


# ==========================================================
# CONVICTION BAND
# ==========================================================

def conviction_band(conviction):

    conviction = float(conviction)

    if conviction >= 90:
        return "90+"

    if conviction >= 80:
        return "80-89"

    if conviction >= 70:
        return "70-79"

    if conviction >= 60:
        return "60-69"

    return "BELOW_60"


# ==========================================================
# LOAD HISTORY
# ==========================================================

def load_historical_predictions():

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

            timestamp,
            ticker,
            price,
            conviction,
            market_score,
            news_score,
            risk,
            trend,

            return_1d,
            return_after_5d,
            return_after_20d

        FROM predictions

        WHERE strategy_version = ?

        ORDER BY timestamp DESC

        LIMIT ?
        """,
        (
            STRATEGY_VERSION,
            HISTORICAL_LIMIT
        )
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ==========================================================
# HISTORICAL PERFORMANCE
# ==========================================================

def summarize_historical_performance(rows):

    summary = {

        "total_prediction_rows":
            len(rows),

        "graded_1d":
            0,

        "graded_5d":
            0,

        "graded_20d":
            0,

        "overall":
            {},

        "conviction_bands":
            {},

        "risk_levels":
            {}
    }


    # ======================================================
    # OVERALL
    # ======================================================

    returns_1d = []

    returns_5d = []

    returns_20d = []


    for row in rows:

        r1 = safe_float(
            row["return_1d"]
        )

        r5 = safe_float(
            row["return_after_5d"]
        )

        r20 = safe_float(
            row["return_after_20d"]
        )


        if r1 is not None:
            returns_1d.append(r1)

        if r5 is not None:
            returns_5d.append(r5)

        if r20 is not None:
            returns_20d.append(r20)


    summary[
        "graded_1d"
    ] = len(returns_1d)

    summary[
        "graded_5d"
    ] = len(returns_5d)

    summary[
        "graded_20d"
    ] = len(returns_20d)


    summary[
        "overall"
    ] = {

        "avg_return_1d":
            average_or_none(
                returns_1d
            ),

        "avg_return_5d":
            average_or_none(
                returns_5d
            ),

        "avg_return_20d":
            average_or_none(
                returns_20d
            )
    }


    # ======================================================
    # CONVICTION BANDS
    # ======================================================

    band_data = {}


    for row in rows:

        conviction = safe_float(
            row["conviction"]
        )

        if conviction is None:
            continue


        band = conviction_band(
            conviction
        )


        if band not in band_data:

            band_data[band] = {

                "count":
                    0,

                "return_1d":
                    [],

                "return_5d":
                    [],

                "return_20d":
                    []
            }


        bucket = band_data[band]

        bucket["count"] += 1


        r1 = safe_float(
            row["return_1d"]
        )

        r5 = safe_float(
            row["return_after_5d"]
        )

        r20 = safe_float(
            row["return_after_20d"]
        )


        if r1 is not None:
            bucket[
                "return_1d"
            ].append(r1)

        if r5 is not None:
            bucket[
                "return_5d"
            ].append(r5)

        if r20 is not None:
            bucket[
                "return_20d"
            ].append(r20)


    for band, bucket in band_data.items():

        summary[
            "conviction_bands"
        ][band] = {

            "prediction_count":
                bucket["count"],

            "graded_1d":
                len(
                    bucket[
                        "return_1d"
                    ]
                ),

            "graded_5d":
                len(
                    bucket[
                        "return_5d"
                    ]
                ),

            "graded_20d":
                len(
                    bucket[
                        "return_20d"
                    ]
                ),

            "avg_return_1d":
                average_or_none(
                    bucket[
                        "return_1d"
                    ]
                ),

            "avg_return_5d":
                average_or_none(
                    bucket[
                        "return_5d"
                    ]
                ),

            "avg_return_20d":
                average_or_none(
                    bucket[
                        "return_20d"
                    ]
                )
        }


    # ======================================================
    # RISK LEVELS
    # ======================================================

    risk_data = {}


    for row in rows:

        risk = str(
            row["risk"]
        ).upper()


        if risk not in risk_data:

            risk_data[risk] = {

                "count":
                    0,

                "return_1d":
                    [],

                "return_5d":
                    [],

                "return_20d":
                    []
            }


        bucket = risk_data[risk]

        bucket["count"] += 1


        r1 = safe_float(
            row["return_1d"]
        )

        r5 = safe_float(
            row["return_after_5d"]
        )

        r20 = safe_float(
            row["return_after_20d"]
        )


        if r1 is not None:
            bucket[
                "return_1d"
            ].append(r1)

        if r5 is not None:
            bucket[
                "return_5d"
            ].append(r5)

        if r20 is not None:
            bucket[
                "return_20d"
            ].append(r20)


    for risk, bucket in risk_data.items():

        summary[
            "risk_levels"
        ][risk] = {

            "prediction_count":
                bucket["count"],

            "graded_1d":
                len(
                    bucket[
                        "return_1d"
                    ]
                ),

            "graded_5d":
                len(
                    bucket[
                        "return_5d"
                    ]
                ),

            "graded_20d":
                len(
                    bucket[
                        "return_20d"
                    ]
                ),

            "avg_return_1d":
                average_or_none(
                    bucket[
                        "return_1d"
                    ]
                ),

            "avg_return_5d":
                average_or_none(
                    bucket[
                        "return_5d"
                    ]
                ),

            "avg_return_20d":
                average_or_none(
                    bucket[
                        "return_20d"
                    ]
                )
        }


    return summary


# ==========================================================
# DETERMINISTIC EVIDENCE GATE
# ==========================================================

def evaluate_algorithm_evidence(
    historical_summary
):

    reasons = []


    total_rows = historical_summary[
        "total_prediction_rows"
    ]

    graded_5d = historical_summary[
        "graded_5d"
    ]

    graded_20d = historical_summary[
        "graded_20d"
    ]


    if (
        total_rows
        < MIN_TOTAL_ROWS_FOR_ALGO_CHANGE
    ):

        reasons.append(

            f"Only {total_rows} historical rows; "
            f"minimum is "
            f"{MIN_TOTAL_ROWS_FOR_ALGO_CHANGE}."
        )


    if (
        graded_5d
        < MIN_GRADED_5D_FOR_ALGO_CHANGE
    ):

        reasons.append(

            f"Only {graded_5d} graded 5D outcomes; "
            f"minimum is "
            f"{MIN_GRADED_5D_FOR_ALGO_CHANGE}."
        )


    if (
        graded_20d
        < MIN_GRADED_20D_FOR_ALGO_CHANGE
    ):

        reasons.append(

            f"Only {graded_20d} graded 20D outcomes; "
            f"minimum is "
            f"{MIN_GRADED_20D_FOR_ALGO_CHANGE}."
        )


    passed = (
        len(reasons) == 0
    )


    return {

        "passed":
            passed,

        "reasons":
            reasons,

        "requirements": {

            "minimum_total_rows":
                MIN_TOTAL_ROWS_FOR_ALGO_CHANGE,

            "minimum_graded_5d":
                MIN_GRADED_5D_FOR_ALGO_CHANGE,

            "minimum_graded_20d":
                MIN_GRADED_20D_FOR_ALGO_CHANGE
        }
    }


# ==========================================================
# CURRENT SIGNAL SUMMARY
# ==========================================================

def build_signal_summary(
    predictions
):

    ranked = sorted(

        predictions,

        key=lambda row:
            float(
                row["conviction"]
            ),

        reverse=True
    )


    results = []


    for row in ranked:

        ticker = str(
            row["ticker"]
        ).upper()

        conviction = safe_float(
            row["conviction"]
        )

        risk = str(
            row["risk"]
        ).upper()


        hard_blocked = (
            risk in BLOCKED_RISK_LEVELS
        )


        buy_eligible = (

            conviction is not None

            and

            conviction > MIN_CONVICTION

            and

            not hard_blocked

            and

            ticker not in {
                "SPY",
                "QQQ"
            }
        )


        results.append({

            "ticker":
                ticker,

            "conviction":
                conviction,

            "market_score":
                safe_float(
                    row[
                        "market_score"
                    ]
                ),

            "news_score":
                safe_float(
                    row[
                        "news_score"
                    ]
                ),

            "risk":
                risk,

            "trend":
                row["trend"],

            "hard_risk_blocked":
                hard_blocked,

            "new_buy_eligible_before_portfolio_constraints":
                buy_eligible
        })


    return {

        "prediction_count":
            len(predictions),

        "ranked_signals":
            results
    }


# ==========================================================
# CURRENT PORTFOLIO FACTS
# ==========================================================

def build_portfolio_summary(
    account_state,
    predictions
):

    prediction_map = {

        row["ticker"]:
            row

        for row in predictions
    }


    equity = float(
        account_state["equity"]
    )

    cash = float(
        account_state["cash"]
    )

    invested = float(
        account_state[
            "current_exposure"
        ]
    )


    if equity > 0:

        cash_percent = (
            cash
            / equity
            * 100
        )

        invested_percent = (
            invested
            / equity
            * 100
        )

    else:

        cash_percent = 0.0

        invested_percent = 0.0


    # ======================================================
    # CASH CLASSIFICATION
    # ======================================================

    if cash_percent >= 50:

        cash_status = (
            "HIGH_CASH"
        )

    elif cash_percent >= 20:

        cash_status = (
            "MODERATE_CASH"
        )

    else:

        cash_status = (
            "LOW_CASH"
        )


    positions = []


    for position in account_state[
        "positions"
    ]:

        ticker = str(
            position.symbol
        ).upper()


        prediction = (
            prediction_map.get(
                ticker
            )
        )


        market_value = safe_float(
            position.market_value
        )


        unrealized_pl = safe_float(
            position.unrealized_pl
        )


        unrealized_plpc = safe_float(
            position.unrealized_plpc
        )


        if unrealized_plpc is not None:

            unrealized_pl_percent = (
                unrealized_plpc
                * 100
            )

        else:

            unrealized_pl_percent = None


        if (
            equity > 0
            and
            market_value is not None
        ):

            weight_percent = (

                market_value
                / equity
                * 100
            )

        else:

            weight_percent = None


        positions.append({

            "ticker":
                ticker,

            "market_value":
                market_value,

            "portfolio_weight_percent":
                weight_percent,

            "unrealized_pl":
                unrealized_pl,

            "unrealized_pl_percent":
                unrealized_pl_percent,

            "current_conviction":
                (
                    safe_float(
                        prediction[
                            "conviction"
                        ]
                    )

                    if prediction

                    else None
                ),

            "current_risk":
                (
                    str(
                        prediction[
                            "risk"
                        ]
                    ).upper()

                    if prediction

                    else None
                ),

            "current_trend":
                (
                    prediction[
                        "trend"
                    ]

                    if prediction

                    else None
                )
        })


    # ======================================================
    # DIVERSIFICATION FACTS
    # ======================================================

    diversification = (
        build_exposure_state(
            account_state[
                "positions"
            ]
        )
    )


    sectors = {}

    clusters = {}


    if equity > 0:

        for (
            sector,
            value
        ) in diversification[
            "sectors"
        ].items():

            percent = (
                value
                / equity
                * 100
            )


            sectors[
                sector
            ] = {

                "exposure_percent":
                    percent,

                "hard_limit_percent":
                    MAX_SECTOR_PERCENT
                    * 100,

                "over_limit":
                    (
                        percent
                        >
                        MAX_SECTOR_PERCENT
                        * 100
                    )
            }


        for (
            cluster,
            value
        ) in diversification[
            "clusters"
        ].items():

            percent = (
                value
                / equity
                * 100
            )


            limit = (
                CLUSTER_LIMITS.get(
                    cluster
                )
            )


            clusters[
                cluster
            ] = {

                "exposure_percent":
                    percent,

                "hard_limit_percent":
                    (
                        limit * 100
                        if limit is not None
                        else None
                    ),

                "over_limit":
                    (
                        percent
                        > limit * 100

                        if limit is not None

                        else False
                    )
            }


    return {

        "equity":
            equity,

        "cash":
            cash,

        "invested":
            invested,

        "cash_percent_of_equity":
            cash_percent,

        "invested_percent_of_equity":
            invested_percent,

        "cash_status":
            cash_status,

        "number_of_positions":
            len(
                account_state[
                    "positions"
                ]
            ),

        "positions":
            positions,

        "sector_exposure":
            sectors,

        "cluster_exposure":
            clusters
    }


# ==========================================================
# CALL QWEN
# ==========================================================

def ask_cio(context):

    system_prompt = """
You are the Chief Investment Officer of an experimental
PAPER-TRADING quantitative investment system.

Python has already calculated all numerical facts.

The deterministic facts provided to you are AUTHORITATIVE.

Do NOT reinterpret percentages.

For example:

cash_percent_of_equity = 70

means 70% of equity is CASH.

Do not call that a low cash position.

You are an INTERPRETER and RESEARCH SUPERVISOR.

You may:

- identify portfolio concerns
- interpret current signals
- recommend advisory portfolio actions
- identify hypotheses worth investigating

You may NOT:

- override hard risk rules
- recommend margin
- recommend leverage
- recommend options
- recommend short selling
- modify production code
- claim statistical significance
- decide whether evidence is sufficient
- promote an algorithm

If the deterministic evidence gate says evidence_passed=false,
algorithm changes MUST be treated only as research hypotheses.

Return ONLY valid JSON.
"""


    user_prompt = f"""
Review this system state:

{json.dumps(context, indent=2)}

Return exactly this JSON structure:

{{
    "market_stance": "string",

    "portfolio_quality": "string",

    "portfolio_summary": "string",

    "concerns": [
        "string"
    ],

    "portfolio_recommendations": [
        {{
            "ticker": "string",

            "action":
                "HOLD | WATCH | REDUCE | EXIT | CONSIDER_BUY",

            "reason": "string"
        }}
    ],

    "system_observations": [
        "string"
    ],

    "algorithm_change_recommended": true,

    "algorithm_hypothesis":
        "string or NONE",

    "proposed_challenger_experiment":
        "string or NONE",

    "evidence_level":
        "INSUFFICIENT | WEAK | MODERATE | STRONG",

    "confidence":
        0.0
}}

Rules:

1. Do not recommend CONSIDER_BUY for anything marked
   hard_risk_blocked=true.

2. Do not recommend filling cash simply because cash exists.

3. Current unrealized P/L alone is not sufficient reason
   to buy or sell.

4. If evidence_passed=false, algorithm changes are only
   hypotheses, not actionable recommendations.

5. Be conservative when sample sizes are small.
"""


    payload = {

        "model":
            MODEL,

        "stream":
            False,

        "think":
            False,

        "format":
            "json",

        "messages": [

            {
                "role":
                    "system",

                "content":
                    system_prompt
            },

            {
                "role":
                    "user",

                "content":
                    user_prompt
            }
        ],

        "options": {

            "temperature":
                0,

            "seed":
                42
        }
    }


    response = requests.post(

        OLLAMA_URL,

        json=payload,

        timeout=180
    )


    response.raise_for_status()


    raw = response.json()


    return json.loads(

        raw[
            "message"
        ][
            "content"
        ]
    )


# ==========================================================
# VALIDATE CIO PORTFOLIO RECOMMENDATIONS
# ==========================================================

def validate_portfolio_recommendations(
    report,
    predictions,
    account_state
):

    prediction_map = {

        str(
            row["ticker"]
        ).upper():
            row

        for row in predictions
    }


    held_symbols = {

        str(
            position.symbol
        ).upper()

        for position in account_state[
            "positions"
        ]
    }


    validated = []


    for recommendation in report.get(
        "portfolio_recommendations",
        []
    ):

        ticker = str(
            recommendation.get(
                "ticker",
                ""
            )
        ).upper()


        requested_action = str(
            recommendation.get(
                "action",
                "WATCH"
            )
        ).upper()


        reason = str(
            recommendation.get(
                "reason",
                ""
            )
        )


        final_action = (
            requested_action
        )


        valid = True

        notes = []


        prediction = (
            prediction_map.get(
                ticker
            )
        )


        # ==================================================
        # UNKNOWN TICKER
        # ==================================================

        if prediction is None:

            valid = False

            notes.append(
                "Ticker has no current prediction."
            )


        # ==================================================
        # ACTIONS REQUIRING AN EXISTING POSITION
        # ==================================================

        if requested_action in {
            "HOLD",
            "REDUCE",
            "EXIT"
        }:

            if ticker not in held_symbols:

                valid = False

                notes.append(
                    "Action requires an existing position."
                )


        # ==================================================
        # NEW BUY VALIDATION
        # ==================================================

        if (
            requested_action
            == "CONSIDER_BUY"
        ):

            if ticker in held_symbols:

                valid = False

                notes.append(
                    "Ticker is already held."
                )


            if prediction is not None:

                conviction = safe_float(
                    prediction[
                        "conviction"
                    ]
                )


                risk = str(
                    prediction[
                        "risk"
                    ]
                ).upper()


                if risk in BLOCKED_RISK_LEVELS:

                    valid = False

                    notes.append(

                        f"Hard risk engine blocks "
                        f"{risk} risk."
                    )


                if (
                    conviction is None
                    or
                    conviction <= MIN_CONVICTION
                ):

                    valid = False

                    notes.append(

                        f"Conviction does not exceed "
                        f"{MIN_CONVICTION:.1f}."
                    )


            if ticker in {
                "SPY",
                "QQQ"
            }:

                valid = False

                notes.append(
                    "Benchmark ETF is not an "
                    "individual-stock candidate."
                )


        # ==================================================
        # INVALID RECOMMENDATION
        # ==================================================

        if not valid:

            final_action = (
                "BLOCKED"
            )


        validated.append({

            "ticker":
                ticker,

            "requested_action":
                requested_action,

            "final_action":
                final_action,

            "valid":
                valid,

            "reason":
                reason,

            "validation_notes":
                notes
        })


    return validated


# ==========================================================
# VALIDATE ALGORITHM SUPERVISION
# ==========================================================

def validate_algorithm_recommendation(
    report,
    evidence_gate
):

    raw_recommendation = bool(
        report.get(
            "algorithm_change_recommended",
            False
        )
    )


    hypothesis = str(
        report.get(
            "algorithm_hypothesis",
            "NONE"
        )
    )


    challenger = str(
        report.get(
            "proposed_challenger_experiment",
            "NONE"
        )
    )


    confidence = safe_float(
        report.get(
            "confidence",
            0
        )
    )


    if confidence is None:

        confidence = 0.0


    confidence = max(
        0.0,
        min(
            confidence,
            1.0
        )
    )


    # ======================================================
    # EVIDENCE GATE FAILED
    # ======================================================

    if not evidence_gate[
        "passed"
    ]:

        return {

            "qwen_requested_change":
                raw_recommendation,

            "algorithm_change_recommended":
                False,

            "evidence_level":
                "INSUFFICIENT",

            "confidence":
                min(
                    confidence,
                    0.35
                ),

            "research_hypothesis":
                hypothesis,

            "proposed_challenger_experiment":
                "NONE",

            "status":
                "RESEARCH_ONLY",

            "gate_reasons":
                evidence_gate[
                    "reasons"
                ]
        }


    # ======================================================
    # EVIDENCE GATE PASSED
    #
    # Even here this only permits creating a
    # challenger experiment.
    #
    # It NEVER authorizes production modification.
    # ======================================================

    return {

        "qwen_requested_change":
            raw_recommendation,

        "algorithm_change_recommended":
            raw_recommendation,

        "evidence_level":
            report.get(
                "evidence_level",
                "WEAK"
            ),

        "confidence":
            confidence,

        "research_hypothesis":
            hypothesis,

        "proposed_challenger_experiment":
            (
                challenger

                if raw_recommendation

                else "NONE"
            ),

        "status":
            (
                "CHALLENGER_RESEARCH_ALLOWED"

                if raw_recommendation

                else "NO_CHANGE"
            ),

        "gate_reasons":
            []
    }


# ==========================================================
# PRINT VALIDATED CIO REPORT
# ==========================================================

def print_validated_report(
    report,
    validated_recommendations,
    validated_algorithm,
    portfolio_facts
):

    print()
    print(
        "=============================================================="
    )

    print(
        "               VALIDATED CIO ASSESSMENT"
    )

    print(
        "=============================================================="
    )


    print(
        f"Market stance: "
        f"{report.get('market_stance')}"
    )


    print(
        f"Portfolio quality: "
        f"{report.get('portfolio_quality')}"
    )


    # ======================================================
    # AUTHORITATIVE PORTFOLIO FACTS
    # ======================================================

    print()
    print(
        "DETERMINISTIC PORTFOLIO FACTS"
    )

    print(
        "--------------------------------------------------------------"
    )


    print(
        f"Cash: "
        f"${portfolio_facts['cash']:,.2f} "
        f"({portfolio_facts['cash_percent_of_equity']:.2f}%)"
    )


    print(
        f"Invested: "
        f"${portfolio_facts['invested']:,.2f} "
        f"({portfolio_facts['invested_percent_of_equity']:.2f}%)"
    )


    print(
        f"Cash classification: "
        f"{portfolio_facts['cash_status']}"
    )


    print(
        f"Positions: "
        f"{portfolio_facts['number_of_positions']}"
    )


    print()
    print(
        "CIO SUMMARY"
    )

    print(
        "--------------------------------------------------------------"
    )

    print(
        report.get(
            "portfolio_summary"
        )
    )


    # ======================================================
    # CONCERNS
    # ======================================================

    print()
    print(
        "CONCERNS"
    )

    print(
        "--------------------------------------------------------------"
    )


    concerns = report.get(
        "concerns",
        []
    )


    if concerns:

        for concern in concerns:

            print(
                f"- {concern}"
            )

    else:

        print(
            "- None."
        )


    # ======================================================
    # VALIDATED PORTFOLIO RECOMMENDATIONS
    # ======================================================

    print()
    print(
        "VALIDATED PORTFOLIO RECOMMENDATIONS"
    )

    print(
        "--------------------------------------------------------------"
    )


    if not validated_recommendations:

        print(
            "No recommendations."
        )


    for item in validated_recommendations:

        print()

        print(
            f"{item['ticker']} "
            f"→ "
            f"{item['final_action']}"
        )


        if (
            item[
                "requested_action"
            ]
            != item[
                "final_action"
            ]
        ):

            print(
                f"  Qwen requested: "
                f"{item['requested_action']}"
            )


        print(
            f"  CIO reason: "
            f"{item['reason']}"
        )


        for note in item[
            "validation_notes"
        ]:

            print(
                f"  VALIDATOR: "
                f"{note}"
            )


    # ======================================================
    # OBSERVATIONS
    # ======================================================

    print()
    print(
        "SYSTEM OBSERVATIONS"
    )

    print(
        "--------------------------------------------------------------"
    )


    observations = report.get(
        "system_observations",
        []
    )


    if observations:

        for observation in observations:

            print(
                f"- {observation}"
            )

    else:

        print(
            "- None."
        )


    # ======================================================
    # ALGORITHM SUPERVISION
    # ======================================================

    print()
    print(
        "ALGORITHM SUPERVISION"
    )

    print(
        "--------------------------------------------------------------"
    )


    print(
        f"Qwen requested change: "
        f"{validated_algorithm['qwen_requested_change']}"
    )


    print(
        f"Validated change recommendation: "
        f"{validated_algorithm['algorithm_change_recommended']}"
    )


    print(
        f"Status: "
        f"{validated_algorithm['status']}"
    )


    print(
        f"Evidence level: "
        f"{validated_algorithm['evidence_level']}"
    )


    print(
        f"Validated confidence: "
        f"{validated_algorithm['confidence']:.2f}"
    )


    print()
    print(
        "Research hypothesis:"
    )

    print(
        validated_algorithm[
            "research_hypothesis"
        ]
    )


    print()
    print(
        "Proposed challenger:"
    )

    print(
        validated_algorithm[
            "proposed_challenger_experiment"
        ]
    )


    if validated_algorithm[
        "gate_reasons"
    ]:

        print()
        print(
            "EVIDENCE GATE BLOCKERS"
        )

        print(
            "--------------------------------------------------------------"
        )


        for reason in validated_algorithm[
            "gate_reasons"
        ]:

            print(
                f"- {reason}"
            )


    print()
    print(
        "=============================================================="
    )

    print(
        "CIO IS ADVISORY ONLY"
    )

    print(
        "HARD RISK RULES OVERRIDE QWEN"
    )

    print(
        "ALGORITHM CHANGES REQUIRE CHALLENGER TESTING"
    )

    print(
        "NO ORDERS PLACED"
    )

    print(
        "NO CODE MODIFIED"
    )

    print(
        "=============================================================="
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
        "               META BRAIN / CIO v0.2"
    )

    print(
        "=============================================================="
    )

    print(
        "QWEN SUPERVISION + DETERMINISTIC VALIDATION"
    )

    print(
        "NO TRADING OR SELF-MODIFICATION"
    )


    # ======================================================
    # CURRENT DATA
    # ======================================================

    predictions = (
        get_latest_predictions()
    )


    if not predictions:

        print()
        print(
            "No current predictions found."
        )

        return


    account_state = (
        get_account_state()
    )


    historical_rows = (
        load_historical_predictions()
    )


    historical_summary = (
        summarize_historical_performance(
            historical_rows
        )
    )


    evidence_gate = (
        evaluate_algorithm_evidence(
            historical_summary
        )
    )


    portfolio_facts = (
        build_portfolio_summary(
            account_state,
            predictions
        )
    )


    signal_facts = (
        build_signal_summary(
            predictions
        )
    )


    # ======================================================
    # CONTEXT GIVEN TO QWEN
    # ======================================================

    context = {

        "production_strategy":
            STRATEGY_VERSION,

        "deterministic_portfolio_facts":
            portfolio_facts,

        "deterministic_signal_facts":
            signal_facts,

        "historical_performance":
            historical_summary,

        "algorithm_evidence_gate": {

            "evidence_passed":
                evidence_gate[
                    "passed"
                ],

            "reasons":
                evidence_gate[
                    "reasons"
                ],

            "requirements":
                evidence_gate[
                    "requirements"
                ]
        },

        "hard_constraints": {

            "cash_only":
                True,

            "long_only":
                True,

            "margin_allowed":
                False,

            "leverage_allowed":
                False,

            "shorts_allowed":
                False,

            "options_allowed":
                False,

            "max_single_stock_percent":
                10,

            "max_total_portfolio_exposure_percent":
                90,

            "minimum_cash_reserve_percent":
                10
        }
    }


    # ======================================================
    # DISPLAY INPUT QUALITY
    # ======================================================

    print()
    print(
        "AUTHORITATIVE DATA"
    )

    print(
        "--------------------------------------------------------------"
    )


    print(
        f"Current predictions: "
        f"{len(predictions)}"
    )


    print(
        f"Current positions: "
        f"{len(account_state['positions'])}"
    )


    print(
        f"Cash percent: "
        f"{portfolio_facts['cash_percent_of_equity']:.2f}%"
    )


    print(
        f"Invested percent: "
        f"{portfolio_facts['invested_percent_of_equity']:.2f}%"
    )


    print(
        f"Historical rows: "
        f"{historical_summary['total_prediction_rows']}"
    )


    print(
        f"1D graded: "
        f"{historical_summary['graded_1d']}"
    )


    print(
        f"5D graded: "
        f"{historical_summary['graded_5d']}"
    )


    print(
        f"20D graded: "
        f"{historical_summary['graded_20d']}"
    )


    print(
        f"Algorithm evidence gate: "
        f"{evidence_gate['passed']}"
    )


    # ======================================================
    # CONSULT QWEN
    # ======================================================

    print()
    print(
        f"Consulting local CIO: "
        f"{MODEL}"
    )


    try:

        raw_report = (
            ask_cio(
                context
            )
        )

    except Exception as error:

        print()
        print(
            "META BRAIN FAILED"
        )

        print(
            f"Error: {error}"
        )

        return


    # ======================================================
    # DETERMINISTIC VALIDATION
    # ======================================================

    validated_recommendations = (
        validate_portfolio_recommendations(

            raw_report,

            predictions,

            account_state
        )
    )


    validated_algorithm = (
        validate_algorithm_recommendation(

            raw_report,

            evidence_gate
        )
    )


    # ======================================================
    # FINAL REPORT
    # ======================================================

    print_validated_report(

        raw_report,

        validated_recommendations,

        validated_algorithm,

        portfolio_facts
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    main()