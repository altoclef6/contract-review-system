[CmdletBinding()]
param(
    [string]$OutputDirectory = "build\desktop-backend"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$spec = Join-Path $projectRoot "desktop\contract-review-backend.spec"
$output = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
$work = Join-Path $projectRoot "build\pyinstaller-work"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found: $python"
}

& $python -m PyInstaller --version
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is missing from the project virtual environment."
}

New-Item -ItemType Directory -Force -Path $output | Out-Null
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $output `
    --workpath $work `
    $spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller backend build failed with exit code $LASTEXITCODE."
}

$executable = Join-Path $output "contract-review-backend\contract-review-backend.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Expected backend executable was not produced: $executable"
}

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $executable
Write-Output "DESKTOP_BACKEND=$executable"
Write-Output "SHA256=$($hash.Hash)"

