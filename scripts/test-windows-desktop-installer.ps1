param(
    [Parameter(Mandatory)]
    [string]$Installer,
    [string]$InstallDirectory = "$env:TEMP\ContractReviewDesktopSmoke"
)

$ErrorActionPreference = "Stop"
$installerPath = (Resolve-Path $Installer).Path
$beforeBackend = @(Get-Process contract-review-backend -ErrorAction SilentlyContinue).Id

$install = Start-Process $installerPath `
    -ArgumentList "/S", "/D=$InstallDirectory" `
    -Wait -PassThru -WindowStyle Hidden
if ($install.ExitCode -ne 0) { throw "Installer exited with $($install.ExitCode)." }

$appPath = Join-Path $InstallDirectory "ContractReviewDesktop.exe"
$backendPath = Join-Path $InstallDirectory "resources\backend\contract-review-backend.exe"
$pythonDll = Join-Path $InstallDirectory "resources\backend\_internal\python312.dll"
foreach ($path in @($appPath, $backendPath, $pythonDll)) {
    if (-not (Test-Path $path)) { throw "Installed file is missing: $path" }
}

$app = Start-Process $appPath -PassThru
try {
    $deadline = (Get-Date).AddSeconds(75)
    $backend = $null
    do {
        Start-Sleep -Milliseconds 500
        $backend = Get-Process contract-review-backend -ErrorAction SilentlyContinue |
            Where-Object { $_.Id -notin $beforeBackend } |
            Select-Object -First 1
    } until ($backend -or (Get-Date) -ge $deadline -or $app.HasExited)
    if (-not $backend) { throw "Desktop backend did not start." }

    do {
        $listeners = @(Get-NetTCPConnection -OwningProcess $backend.Id -State Listen -ErrorAction SilentlyContinue)
        if ($listeners.Count -eq 0) { Start-Sleep -Milliseconds 500 }
    } until ($listeners.Count -gt 0 -or (Get-Date) -ge $deadline -or $app.HasExited)
    if ($listeners.Count -ne 1 -or $listeners[0].LocalAddress -ne "127.0.0.1") {
        throw "Backend must have exactly one loopback listener."
    }

    if (-not $app.CloseMainWindow()) { throw "Unable to request normal app close." }
    if (-not $app.WaitForExit(15000)) { throw "Desktop app did not exit normally." }
    Start-Sleep -Seconds 2
    if (Get-Process -Id $backend.Id -ErrorAction SilentlyContinue) {
        throw "Backend remained after the desktop app exited."
    }
}
finally {
    if (-not $app.HasExited) { Stop-Process -Id $app.Id -Force }
}

$uninstaller = Join-Path $InstallDirectory "uninstall.exe"
$uninstall = Start-Process $uninstaller -ArgumentList "/S" -Wait -PassThru -WindowStyle Hidden
if ($uninstall.ExitCode -ne 0) { throw "Uninstaller exited with $($uninstall.ExitCode)." }
if (Test-Path $InstallDirectory) { throw "Program directory remained after uninstall." }

Write-Output "INSTALLER_SMOKE=PASS"
