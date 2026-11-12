@echo off
setlocal
set SCRIPT_DIR=%~dp0
set PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    set PYTHON=python
)

if "%~1"=="" (
    "%PYTHON%" "%SCRIPT_DIR%main.py" chat
) else (
    "%PYTHON%" "%SCRIPT_DIR%main.py" code %*
)
