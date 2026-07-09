$processes = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
    Where-Object {
        $_.CommandLine -like "*contract_review.main:app*" -or
        $_.CommandLine -like "*uvicorn*contract_review*"
    }

if (-not $processes) {
    Write-Host "No running contract review backend process found."
    exit 0
}

foreach ($process in $processes) {
    try {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped process $($process.ProcessId)"
    } catch {
        Write-Host "Process $($process.ProcessId) is already stopped or cannot be stopped."
    }
}
