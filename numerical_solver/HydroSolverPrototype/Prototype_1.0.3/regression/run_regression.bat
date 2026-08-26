@echo off
cd /d "%~dp0\.."
python .\regression\run_regression.py %*
exit /b %ERRORLEVEL%
