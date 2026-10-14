import os

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

from risk_engine import (
    evaluate_new_position,
    print_risk_result
)


# ==========================================================
# SETTINGS
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
# PAPER ACCOUNT CLIENT
# ==========================================================

trading_client = TradingClient(
    API_KEY,
    SECRET_KEY,

    # CRITICAL:
    # This connects only to Alpaca Paper.
    paper=True
)


# ==========================================================
# GET PAPER ACCOUNT
# ==========================================================

account = trading_client.get_account()

positions = (
    trading_client.get_all_positions()
)


# ==========================================================
# ACCOUNT VALUES
# ==========================================================

account_equity = float(
    account.equity
)

cash = float(
    account.cash
)

buying_power = float(
    account.buying_power
)


# ==========================================================
# CURRENT PORTFOLIO EXPOSURE
# ==========================================================

current_exposure = 0.0


for position in positions:

    market_value = abs(
        float(
            position.market_value
        )
    )

    current_exposure += (
        market_value
    )


open_positions_count = len(
    positions
)


# ==========================================================
# DISPLAY PAPER ACCOUNT
# ==========================================================

print()
print(
    "=============================================================="
)

print(
    "                 ALPACA PAPER ACCOUNT"
)

print(
    "=============================================================="
)

print(
    f"Equity:          "
    f"${account_equity:,.2f}"
)

print(
    f"Cash:            "
    f"${cash:,.2f}"
)

print(
    f"Buying power:    "
    f"${buying_power:,.2f}"
)

print(
    f"Current exposure:"
    f" ${current_exposure:,.2f}"
)

print(
    f"Open positions:  "
    f"{open_positions_count}"
)

print(
    f"Trading blocked: "
    f"{account.trading_blocked}"
)

print(
    "=============================================================="
)


# ==========================================================
# DISPLAY CURRENT POSITIONS
# ==========================================================

if positions:

    print()
    print(
        "CURRENT PAPER POSITIONS"
    )

    print(
        "--------------------------------------------------------------"
    )


    for position in positions:

        print()

        print(
            f"{position.symbol}"
        )

        print(
            f"  Quantity: "
            f"{position.qty}"
        )

        print(
            f"  Market value: "
            f"${float(position.market_value):,.2f}"
        )

        print(
            f"  Current price: "
            f"${float(position.current_price):,.2f}"
        )

        print(
            f"  Unrealized P/L: "
            f"${float(position.unrealized_pl):,.2f}"
        )


else:

    print()
    print(
        "No current paper positions."
    )


# ==========================================================
# TEST CURRENT BRAIN CANDIDATES
# ==========================================================

print()
print(
    "=============================================================="
)

print(
    "             LIVE PAPER ACCOUNT RISK TEST"
)

print(
    "=============================================================="
)

print(
    "READ-ONLY — NO ORDERS WILL BE PLACED"
)


# ==========================================================
# CRM
# ==========================================================

crm_result = evaluate_new_position(

    ticker="CRM",

    conviction=81.3,

    risk="MED",

    account_equity=
        account_equity,

    cash=
        cash,

    current_exposure=
        current_exposure,

    open_positions_count=
        open_positions_count
)


print_risk_result(
    crm_result
)


# ==========================================================
# NFLX
# ==========================================================

nflx_result = evaluate_new_position(

    ticker="NFLX",

    conviction=80.3,

    risk="LOW",

    account_equity=
        account_equity,

    cash=
        cash,

    current_exposure=
        current_exposure,

    open_positions_count=
        open_positions_count
)


print_risk_result(
    nflx_result
)


# ==========================================================
# HIGH-RISK TEST
# ==========================================================

msft_result = evaluate_new_position(

    ticker="MSFT",

    conviction=85.0,

    risk="HIGH",

    account_equity=
        account_equity,

    cash=
        cash,

    current_exposure=
        current_exposure,

    open_positions_count=
        open_positions_count
)


print_risk_result(
    msft_result
)


# ==========================================================
# FINISHED
# ==========================================================

print()
print(
    "=============================================================="
)

print(
    "PAPER ACCOUNT CHECK COMPLETE"
)

print(
    "NO ORDERS WERE PLACED"
)

print(
    "=============================================================="
)