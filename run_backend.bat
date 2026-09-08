@echo off
title AI Sales Automation Platform
echo ==========================================================
echo  Starting AI Sales Automation Platform (Local Console)
echo  Powered by Google Gemini & PostgreSQL / Local-First
echo ==========================================================
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

echo.
echo Launching server at http://127.0.0.1:8000/
echo Web Console: http://127.0.0.1:8000/
echo OpenAPI Docs: http://127.0.0.1:8000/docs
echo.

.venv\Scripts\uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
