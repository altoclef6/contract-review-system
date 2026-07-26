param(
    [string]$RustTarget = "x86_64-pc-windows-msvc",
    [string]$CargoTargetDir = "",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $CargoTargetDir) {
    $CargoTargetDir = Join-Path $repoRoot "build\cargo-desktop"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "dist\windows"
}

foreach ($command in @("python", "pnpm", "cargo")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $command"
    }
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Create .venv and install requirements-dev.txt before building."
}

Push-Location $repoRoot
try {
    & $venvPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
    & $venvPython -m ruff check backend desktop
    if ($LASTEXITCODE -ne 0) { throw "Ruff failed." }
    & $venvPython -m mypy backend
    if ($LASTEXITCODE -ne 0) { throw "Mypy failed." }

    & pnpm --dir frontend install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw "Frontend install failed." }
    & pnpm --dir frontend build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }

    & (Join-Path $repoRoot "scripts\build-desktop-backend.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Backend packaging failed." }

    $backendSource = Join-Path $repoRoot "build\desktop-backend\contract-review-backend"
    $backendResource = Join-Path $repoRoot "desktop\src-tauri\resources\backend"
    if (-not (Test-Path (Join-Path $backendSource "contract-review-backend.exe"))) {
        throw "Packaged backend executable is missing."
    }
    New-Item -ItemType Directory -Force -Path $backendResource | Out-Null
    Copy-Item -Path (Join-Path $backendSource "*") -Destination $backendResource -Recurse -Force

    $env:CARGO_TARGET_DIR = $CargoTargetDir
    Push-Location (Join-Path $repoRoot "desktop\src-tauri")
    try {
        & (Join-Path $repoRoot "frontend\node_modules\.bin\tauri.cmd") build --target $RustTarget
        if ($LASTEXITCODE -ne 0) { throw "Tauri/NSIS build failed." }
    }
    finally {
        Pop-Location
    }

    $releaseDir = Join-Path $CargoTargetDir "$RustTarget\release"
    $installer = Get-ChildItem (Join-Path $releaseDir "bundle\nsis") -Filter "*-setup.exe" |
        Select-Object -First 1
    if (-not $installer) { throw "NSIS installer was not produced." }

    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $installerOut = Join-Path $OutputDir "ContractReviewSetup-x64.exe"
    Copy-Item -LiteralPath $installer.FullName -Destination $installerOut -Force

    $portableDir = Join-Path $OutputDir "ContractReviewPortable-x64"
    New-Item -ItemType Directory -Force -Path $portableDir | Out-Null
    Copy-Item (Join-Path $releaseDir "ContractReviewDesktop.exe") $portableDir -Force
    if (Test-Path (Join-Path $releaseDir "WebView2Loader.dll")) {
        Copy-Item (Join-Path $releaseDir "WebView2Loader.dll") $portableDir -Force
    }
    Copy-Item (Join-Path $releaseDir "backend") $portableDir -Recurse -Force
    $portableZip = Join-Path $OutputDir "ContractReviewPortable-x64.zip"
    Compress-Archive -Path (Join-Path $portableDir "*") -DestinationPath $portableZip -Force

    Get-FileHash $installerOut, $portableZip -Algorithm SHA256 |
        Format-Table Path, Hash -AutoSize
}
finally {
    Pop-Location
}
