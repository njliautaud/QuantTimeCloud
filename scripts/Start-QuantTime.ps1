# QuantTime PowerShell Startup Script
# Run this script to automatically setup and launch QuantTime

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "QuantTime Automated Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.11+ and try again" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Starting QuantTime..." -ForegroundColor Yellow
Write-Host ""

# Run the automated startup script
try {
    python start_quanttime.py
} catch {
    Write-Host "❌ Error running QuantTime startup script" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "QuantTime has stopped." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
