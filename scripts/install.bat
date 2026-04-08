@echo off
REM iLongRun Windows installer wrapper
REM This calls the PowerShell installer
setlocal

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."

echo.
echo  iLongRun Windows Installer
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python not found. Please install Python 3.8+ first.
    echo  Download: https://www.python.org/downloads/
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" %*
