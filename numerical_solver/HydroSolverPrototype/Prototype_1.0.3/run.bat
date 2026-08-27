@echo off
setlocal
if "%~1"=="" (
  echo Usage: run.bat INPUT\My_Model.xlsx [--output OUTPUT_PATH]
  exit /b 2
)
python "%~dp0run_prototype.py" %*
exit /b %ERRORLEVEL%
