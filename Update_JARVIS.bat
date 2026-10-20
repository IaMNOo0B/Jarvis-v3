@echo off
setlocal
cd /d "%~dp0"
title JARVIS v3 - Safe Updater

where git >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed. Update through GitHub Desktop instead.
    pause
    exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo ERROR: This folder is not a Git checkout. Use GitHub Desktop to clone the repository.
    pause
    exit /b 1
)

for /f "delims=" %%B in ('git branch --show-current') do set "CURRENT_BRANCH=%%B"
if not defined CURRENT_BRANCH (
    echo ERROR: Could not identify the current branch. No changes made.
    pause
    exit /b 1
)

git status --porcelain >nul
for /f "delims=" %%S in ('git status --porcelain') do set "DIRTY=1"
if defined DIRTY (
    echo ERROR: Working tree is not clean. Commit or back up your changes before updating.
    echo No pull was attempted; local changes were preserved.
    pause
    exit /b 1
)

echo Current branch: %CURRENT_BRANCH%
echo This performs only a fast-forward pull from its configured upstream.
echo It does not switch branches, reset files, or delete local data.
git pull --ff-only
if errorlevel 1 (
    echo Update failed or no upstream is configured. No reset or forced update was attempted.
    pause
    exit /b 1
)

echo Update completed. Re-run Install_JARVIS.bat if the Python environment is missing.
pause
