@echo off
REM Node-specific environment setup for laptop
REM Generated automatically - DO NOT EDIT MANUALLY

set NODE_NAME=laptop
set PLATFORM=windows
set ARCH=AMD64
set PYTHON_VERSION=3.11

REM Project paths
set QUANTTIME_ROOT=C:\Users\user\Documents\GitHub\QuantTime
set QUANTTIME_DATA=C:\Users\user\Documents\GitHub\QuantTime\data
set QUANTTIME_LOGS=C:\Users\user\Documents\GitHub\QuantTime\logs
set QUANTTIME_CACHE=C:\Users\user\Documents\GitHub\QuantTime\cache
set QUANTTIME_TEMP=C:\Users\user\Documents\GitHub\QuantTime\temp
set QUANTTIME_VENV=C:\Users\user\Documents\GitHub\QuantTime\.venv

REM Ray configuration
set RAY_TEMP_DIR=C:\Users\user\Documents\GitHub\QuantTime\temp\ray
set RAY_LOG_DIR=C:\Users\user\Documents\GitHub\QuantTime\logs\ray
set RAY_DASHBOARD_PORT=8265
set RAY_HEAD_PORT=10001

REM Create directories
if not exist "%QUANTTIME_DATA%" mkdir "%QUANTTIME_DATA%"
if not exist "%QUANTTIME_LOGS%" mkdir "%QUANTTIME_LOGS%"
if not exist "%QUANTTIME_CACHE%" mkdir "%QUANTTIME_CACHE%"
if not exist "%QUANTTIME_TEMP%" mkdir "%QUANTTIME_TEMP%"
if not exist "%RAY_TEMP_DIR%" mkdir "%RAY_TEMP_DIR%"
if not exist "%RAY_LOG_DIR%" mkdir "%RAY_LOG_DIR%"

REM Python path
set PYTHONPATH=%QUANTTIME_ROOT%;%PYTHONPATH%

REM Activate virtual environment
if exist "%QUANTTIME_VENV%\Scripts\activate.bat" (
    call "%QUANTTIME_VENV%\Scripts\activate.bat"
)

echo Environment setup complete for laptop
