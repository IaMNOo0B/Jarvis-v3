@echo off
setlocal
cd /d "%~dp0"
title JARVIS v3 - Installer

echo.
echo  JARVIS v3 setup
echo  ----------------
echo  This creates a local Python environment. It does not download models,
echo  send credentials, or install third-party Python packages.
echo.

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3.12 or newer was not found.
        echo Install 64-bit Python 3.12+ and enable the Python launcher or PATH.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
) else (
    set "PYTHON_CMD=py -3.12"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating isolated environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create the virtual environment.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import tkinter, sqlite3; print('Python, Tkinter and SQLite are available.')"
if errorlevel 1 (
    echo ERROR: Required standard-library components are unavailable.
    echo Reinstall Python with Tcl/Tk support.
    pause
    exit /b 1
)

echo.
echo Setup checks passed.
echo IMPORTANT: Ollama and the configured model are separate prerequisites for local AI chat.
echo.
start "" ".venv\Scripts\pythonw.exe" "Start_JARVIS.pyw"
if errorlevel 1 (
    echo ERROR: Could not start JARVIS. Try Launch_JARVIS.bat for diagnostics.
    pause
    exit /b 1
)
exit /b 0
