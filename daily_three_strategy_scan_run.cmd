@echo off
cd /d "%~dp0"
call .venv\Scripts\python.exe pp_backtest\daily_three_strategy_scan.py
if errorlevel 1 pause
exit /b %errorlevel%
