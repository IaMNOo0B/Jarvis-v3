@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JARVIS v3 - One-Click Launcher

rem Double-click launches immediately. Pass --menu for maintenance tools.
if /i "%~1"=="--menu" goto menu
goto start

:menu
cls
echo.
echo  ==========================================
echo             JARVIS v3 CONTROL
echo  ==========================================
echo.
echo  [1] Start JARVIS
echo  [2] First-time setup / repair environment
echo  [3] Update JARVIS safely
echo  [4] Run diagnostics
echo  [5] Exit
echo.
choice /c 12345 /n /m "Choose 1-5: "
if errorlevel 5 goto end
if errorlevel 4 goto diagnostics
if errorlevel 3 goto update
if errorlevel 2 goto setup
if errorlevel 1 goto start

:setup
call :findpython
if errorlevel 1 goto pausemenu
if not exist ".venv\Scripts\python.exe" (
  echo Creating private Python environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo ERROR: Could not create Python environment.
    goto pausemenu
  )
)
".venv\Scripts\python.exe" -c "import tkinter, sqlite3; print('Python, Tkinter and SQLite: OK')"
if errorlevel 1 (
  echo ERROR: Tkinter or SQLite check failed. Repair/reinstall Python with Tcl/Tk.
  goto pausemenu
)
echo Setup checks passed. No model or third-party package was downloaded.
echo Ollama and the configured model must be installed separately for local AI.
goto pausemenu

:start
if not exist ".venv\Scripts\python.exe" (
  echo First run: setting up the environment...
  call :findpython
  if errorlevel 1 goto pausemenu
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo ERROR: Could not create Python environment.
    goto pausemenu
  )
)
".venv\Scripts\python.exe" -c "import tkinter, sqlite3" >nul 2>&1
if errorlevel 1 (
  echo Environment check failed. Choose option 2 to diagnose or repair it.
  goto pausemenu
)
if not exist "Start_JARVIS.pyw" (
  echo ERROR: Start_JARVIS.pyw is missing from this folder.
  echo Re-clone or restore the repository files; user data was not changed.
  goto pausemenu
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo ERROR: The windowed Python launcher is missing from .venv.
  echo Choose option 2 to diagnose the Python environment.
  goto pausemenu
)
start "" ".venv\Scripts\pythonw.exe" "Start_JARVIS.pyw"
goto end

:update
where git >nul 2>&1
if errorlevel 1 (
  echo Git is not installed. Install GitHub Desktop or Git, then retry.
  goto pausemenu
)
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo This folder is not a Git checkout. Clone the repository using GitHub Desktop.
  goto pausemenu
)
for /f "delims=" %%B in ('git branch --show-current') do set "CURRENT_BRANCH=%%B"
if not defined CURRENT_BRANCH (
  echo Could not identify the current branch. No changes made.
  goto pausemenu
)
set "DIRTY="
for /f "delims=" %%S in ('git status --porcelain') do set "DIRTY=1"
if defined DIRTY (
  echo Local changes detected. Update stopped to protect your work.
  echo Commit or back up changes, then retry. No reset was performed.
  goto pausemenu
)
echo Updating current branch: %CURRENT_BRANCH%
git pull --ff-only
if errorlevel 1 (
  echo Update failed. No reset or forced update was attempted.
  goto pausemenu
)
echo Update completed. Start JARVIS from this menu when ready.
goto pausemenu

:diagnostics
echo.
echo --- Python ---
where py
if not errorlevel 1 py -0p
where python
python --version
echo.
echo --- Git ---
git --version
echo.
echo --- Local environment ---
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version
  ".venv\Scripts\python.exe" -c "import tkinter, sqlite3; print('Tkinter/SQLite: OK')"
) else (
  echo No local environment yet. Choose option 2.
)
echo.
echo --- Ollama ---
where ollama
if not errorlevel 1 ollama --version
goto pausemenu

:findpython
set "PYTHON_CMD="
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_CMD=py -3.12"
  exit /b 0
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_CMD=python"
  exit /b 0
)
echo Python 3.12 or newer was not found. Install 64-bit Python 3.12+ first.
exit /b 1

:pausemenu
echo.
pause
goto menu

:end
endlocal
exit /b 0
