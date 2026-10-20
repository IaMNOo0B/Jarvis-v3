@echo off
setlocal
cd /d "%~dp0"
title JARVIS v3 - Launcher

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import tkinter, sqlite3" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: The local Python environment is missing Tkinter or SQLite.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" "Start_JARVIS.pyw"
    if errorlevel 1 (
        echo.
        echo JARVIS exited with an error. The diagnostic output is shown above.
        pause
        exit /b 1
    )
) else (
    echo No local environment found. Run Install_JARVIS.bat first.
    pause
    exit /b 1
)
