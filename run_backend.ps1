# AI Sales Automation Platform - Local Startup Script
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting AI Sales Automation Platform (Local Console)   " -ForegroundColor Cyan
Write-Host " Powered by Google Gemini & PostgreSQL / SQLite Fallback  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$scriptDir\backend"

$pythonExe = "$scriptDir\backend\.venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "Virtual environment not found at $pythonExe. Creating..." -ForegroundColor Yellow
    py -m venv "$scriptDir\backend\.venv"
    & "$scriptDir\backend\.venv\Scripts\pip.exe" install -r "$scriptDir\backend\requirements.txt"
}

Write-Host "`nLaunching FastAPI application on http://127.0.0.1:8000..." -ForegroundColor Green
Write-Host "Web Console: http://127.0.0.1:8000/" -ForegroundColor Green
Write-Host "OpenAPI Docs: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "`nPress Ctrl+C to stop the server.`n" -ForegroundColor DarkGray

& "$scriptDir\backend\.venv\Scripts\uvicorn.exe" main:app --host 127.0.0.1 --port 8000 --reload
