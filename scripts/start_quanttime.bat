@echo off
echo ========================================
echo QuantTime Automated Startup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ and try again
    pause
    exit /b 1
)

echo Starting QuantTime...
echo.

REM Run the setup script (automatically activates environment and launches)
python setup_quanttime.py

echo.
echo QuantTime has stopped.
pause
