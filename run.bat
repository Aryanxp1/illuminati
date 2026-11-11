@echo off
setlocal
set SCRIPT_DIR=%~dp0
set PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    set PYTHON=python
)

if "%~1"=="" (
    "%PYTHON%" "%SCRIPT_DIR%main.py" chat
    goto :eof
)

if /i "%~1"=="web" (
    start http://localhost:8000
    goto :eof
)

if /i "%~1"=="docs" (
    start http://localhost:8000/overview
    goto :eof
)

"%PYTHON%" "%SCRIPT_DIR%main.py" %*
