$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Write-Host "Starting contract review backend..."
Write-Host "API docs: http://127.0.0.1:8000/docs"
Write-Host "Stop: press Ctrl+C in this window, or run stop_server.ps1"

.\.venv\Scripts\python.exe -m uvicorn contract_review.main:app --reload --app-dir src --host 127.0.0.1 --port 8000
