@echo off
cd /d "%~dp0"
.\.venv\Scripts\python.exe scripts\monitor_vnindex_distribution_session.py --fetch --refresh-ex-vin %*
