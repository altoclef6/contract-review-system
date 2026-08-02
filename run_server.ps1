$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonCommand = if (Test-Path ".\.venv\Scripts\python.exe") {
    (Resolve-Path ".\.venv\Scripts\python.exe").Path
} else {
    $systemPython = Get-Command python -ErrorAction SilentlyContinue
    if (-not $systemPython) {
        Write-Error "Python not found. Install Python 3.11+ or create .venv before starting the backend."
        exit 1
    }
    $systemPython.Source
}

& $pythonCommand -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend dependencies are missing. Run: & '$pythonCommand' -m pip install -r requirements.txt"
    exit 1
}

Write-Host "Starting contract review backend..."
Write-Host "API docs: http://127.0.0.1:8000/docs"
Write-Host "Stop: press Ctrl+C in this window, or run stop_server.ps1"

$env:PYTHONPATH = Join-Path $projectRoot "src"
& $pythonCommand -m uvicorn contract_review.main:app --reload --app-dir src --host 127.0.0.1 --port 8000
