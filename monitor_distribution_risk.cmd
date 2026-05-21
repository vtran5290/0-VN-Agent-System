@echo off
REM Writes JSON + HTML + MD to data\research\market_risk\
cd /d "%~dp0"
.\.venv\Scripts\python.exe -m src.trading.cli distribution-risk --start 2012-01-01 --as-of latest
exit /b %ERRORLEVEL%
