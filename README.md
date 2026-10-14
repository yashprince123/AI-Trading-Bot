# AI Trading Bot

Python research and paper-trading project combining market momentum, news analysis, local AI models through Ollama, prediction tracking, portfolio planning, and risk controls.

## Components

- `combined_brain.py`: combines market signals and AI news analysis.
- `market_brain.py`, `news_brain.py`, `ai_news_brain.py`, and `live_ai_news_brain.py`: individual analysis scripts.
- `prediction_database.py`, `prediction_logger.py`, and `prediction_grader.py`: SQLite prediction storage and grading.
- `risk_engine.py` and `diversification_engine.py`: portfolio constraints and position planning.
- `paper_trade_planner.py`, `portfolio_manager.py`, and the paper executors: Alpaca paper-account workflows.
- `daily_runner.py`: coordinates the daily workflow.
- Momentum strategy and validation scripts: Lumibot backtesting experiments.

## Local setup on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in your local `.env` to your own Alpaca paper-account credentials. Keep that file private.

AI analysis requires Ollama running locally. Check the model settings in the analysis script you plan to use and install that model in Ollama first.

Initialize a new local prediction database:

```powershell
python prediction_database.py
python upgrade_prediction_database.py
```

Review the scripts and their configuration before running a workflow. `run_daily.bat` uses the virtual environment in this project folder. Several scripts contact external data services, and paper-order scripts may submit simulated orders depending on their execution flags.

## Repository contents

This repository contains source code and setup placeholders. Credentials, local account databases, logs, generated reports, archives, and virtual environments are excluded. Dependencies are currently unpinned; a fully reproducible environment has not been established.

This is an experimental project. Backtest or simulated results do not establish future trading performance.
